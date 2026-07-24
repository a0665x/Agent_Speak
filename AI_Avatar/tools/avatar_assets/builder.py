from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping, Sequence

from PIL import Image, ImageDraw

from .images import crop_source, normalize_frame
from .inventory import load_inventory
from .manifest import load_manifest, validate_manifest
from .quality import QualityThresholds, assess_sequence


CLIP_ORDER = (
    "idle_loop",
    "listening_loop",
    "thinking_loop",
    "speaking_loop",
    "happy_loop",
    "error_loop",
)


class PublishError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishResult:
    published: tuple[str, ...]
    manifest_path: Path


@dataclass(frozen=True)
class ExtractionResult:
    transition_frame: Path
    states: Mapping[str, tuple[Path, ...]]


@dataclass(frozen=True)
class ReviewResult:
    report_hashes: Mapping[str, str]
    preview_paths: Mapping[str, Path]


Interpolator = Callable[[Path, Path, str], tuple[Path, ...]]


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def extract_inventory(
    inventory_path: Path,
    sheets_dir: Path,
    candidate_root: Path,
    *,
    reference_width: int = 380,
    reference_height: int = 360,
    background_tolerance: int = 18,
) -> ExtractionResult:
    inventory = load_inventory(inventory_path, sheets_dir)
    images: dict[str, Image.Image] = {}

    def sheet(name: str) -> Image.Image:
        if name not in images:
            images[name] = Image.open(sheets_dir / name).convert("RGBA")
        return images[name]

    def extract(source_name: str, box: tuple[int, int, int, int]) -> Image.Image:
        return normalize_frame(
            crop_source(sheet(source_name), box),
            canvas_size=inventory.canvas,
            anchor=inventory.anchor,
            background_tolerance=background_tolerance,
            reference_width=reference_width,
            reference_height=reference_height,
        )

    transition = extract(
        inventory.transition_source.sheet,
        inventory.transition_source.boxes[0],
    )
    transition_path = candidate_root / "shared/henry_s0.png"
    transition_path.parent.mkdir(parents=True, exist_ok=True)
    transition.save(transition_path)

    state_paths: dict[str, tuple[Path, ...]] = {}
    for state, source in inventory.states.items():
        paths: list[Path] = []
        for index, box in enumerate(source.boxes, start=1):
            destination = (
                candidate_root
                / "extracted"
                / state
                / f"{state}_{index:03d}.png"
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            extract(source.sheet, box).save(destination)
            paths.append(destination)
        state_paths[state] = tuple(paths)
    for image in images.values():
        image.close()
    return ExtractionResult(
        transition_frame=transition_path,
        states=MappingProxyType(state_paths),
    )


def assemble_candidate_loop(
    transition_frame: Path,
    core_frames: Sequence[Path],
    interpolator: Interpolator,
) -> tuple[Path, ...]:
    if not core_frames:
        raise ValueError("candidate loop requires at least one core frame")
    entry = interpolator(transition_frame, core_frames[0], "entry")
    continuous_core: list[Path] = []
    for index, frame in enumerate(core_frames):
        continuous_core.append(frame)
        if index + 1 < len(core_frames):
            continuous_core.extend(
                interpolator(
                    frame,
                    core_frames[index + 1],
                    f"core_{index + 1:03d}",
                )
            )
    exit_frames = interpolator(core_frames[-1], transition_frame, "exit")
    return (
        transition_frame,
        *entry,
        *continuous_core,
        *exit_frames,
        transition_frame,
    )


def _write_preview(frames: Sequence[Path], destination: Path, fps: int) -> None:
    opened = [Image.open(path).convert("RGBA") for path in frames]
    duration = max(1, round(1000 / fps))
    destination.parent.mkdir(parents=True, exist_ok=True)
    opened[0].save(
        destination,
        save_all=True,
        append_images=opened[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )
    for image in opened:
        image.close()


def review_candidate_loops(
    extracted: ExtractionResult,
    candidate_root: Path,
    *,
    interpolator: Interpolator,
    thresholds: QualityThresholds | None = None,
) -> ReviewResult:
    active_thresholds = thresholds or QualityThresholds(
        max_adjacent_delta=0.55,
        max_alpha_growth=0.35,
        max_center_drift=0.12,
        max_baseline_drift=0.04,
    )
    report_hashes: dict[str, str] = {}
    preview_paths: dict[str, Path] = {}
    for state in ("idle", "listening", "thinking", "speaking", "happy", "error"):
        clip_id = f"{state}_loop"

        def scoped_interpolator(
            start: Path,
            end: Path,
            phase: str,
            *,
            state_name: str = state,
        ) -> tuple[Path, ...]:
            return interpolator(start, end, f"{state_name}_{phase}")

        frames = assemble_candidate_loop(
            extracted.transition_frame,
            extracted.states[state],
            scoped_interpolator,
        )
        opened = [Image.open(path).convert("RGBA") for path in frames]
        report = assess_sequence(opened, active_thresholds)
        for image in opened:
            image.close()
        report_hashes[clip_id] = write_review_report(
            candidate_root=candidate_root,
            clip_id=clip_id,
            state=state,
            frame_paths=frames,
            quality_status=report.status,
            metrics=report.metrics,
            failed_rules=report.failed_rules,
        )
        preview = candidate_root / f"previews/{clip_id}.gif"
        _write_preview(frames, preview, fps=12)
        preview_paths[clip_id] = preview
    return ReviewResult(
        report_hashes=MappingProxyType(report_hashes),
        preview_paths=MappingProxyType(preview_paths),
    )


def write_contact_sheet(extracted: ExtractionResult, destination: Path) -> int:
    entries = [
        ("S0", extracted.transition_frame),
        *[
            (state.title(), extracted.states[state][0])
            for state in (
                "idle",
                "listening",
                "thinking",
                "speaking",
                "happy",
                "error",
            )
        ],
    ]
    cell_width = 160
    image_height = 192
    contact = Image.new(
        "RGBA",
        (cell_width * len(entries), image_height),
        (16, 18, 24, 255),
    )
    draw = ImageDraw.Draw(contact)
    for index, (label, path) in enumerate(entries):
        with Image.open(path) as source:
            frame = source.convert("RGBA")
            frame.thumbnail((144, 144), Image.Resampling.LANCZOS)
        x = index * cell_width + (cell_width - frame.width) // 2
        y = 8 + (144 - frame.height)
        contact.alpha_composite(frame, (x, y))
        draw.text((index * cell_width + 12, 164), label, fill=(238, 240, 248, 255))
    destination.parent.mkdir(parents=True, exist_ok=True)
    contact.save(destination)
    return len(entries)


def _inside(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise PublishError(f"path must stay below candidate root: {path}")
    return resolved


def write_review_report(
    *,
    candidate_root: Path,
    clip_id: str,
    state: str,
    frame_paths: Sequence[Path],
    quality_status: str,
    metrics: Mapping[str, float],
    failed_rules: Sequence[str],
) -> str:
    if quality_status not in {"needs_review", "needs_keyframe"}:
        raise PublishError("generated report must await human review")
    if clip_id != f"{state}_loop":
        raise PublishError("clip ID must match state")
    relative_frames = [
        _inside(candidate_root, path).relative_to(candidate_root.resolve()).as_posix()
        for path in frame_paths
    ]
    body = {
        "version": "1.0",
        "clip_id": clip_id,
        "state": state,
        "quality_status": quality_status,
        "frames": relative_frames,
        "metrics": dict(sorted(metrics.items())),
        "failed_rules": list(failed_rules),
    }
    report_hash = hashlib.sha256(_canonical_json(body)).hexdigest()
    report = {**body, "report_sha256": report_hash}
    report_path = candidate_root / f"clips/{state}/report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report_hash


def _load_verified_report(
    candidate_root: Path,
    clip_id: str,
    supplied_hash: str,
) -> dict[str, object]:
    state = clip_id.removesuffix("_loop")
    report_path = candidate_root / f"clips/{state}/report.json"
    if not report_path.is_file():
        raise PublishError(f"{clip_id}: review report is missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise PublishError(f"{clip_id}: review report is invalid")
    stored_hash = report.pop("report_sha256", None)
    actual_hash = hashlib.sha256(_canonical_json(report)).hexdigest()
    if supplied_hash != stored_hash or supplied_hash != actual_hash:
        raise PublishError(f"{clip_id}: review hash does not match candidates")
    if report.get("quality_status") != "needs_review":
        raise PublishError(f"{clip_id}: candidate requires a keyframe")
    if report.get("clip_id") != clip_id or report.get("state") != state:
        raise PublishError(f"{clip_id}: review identity mismatch")
    return report


def _frame_destination(state: str, source: Path) -> tuple[str, Path]:
    frame_id = source.stem
    if frame_id == "henry_s0":
        relative = Path("assets/clips/shared/henry_s0.png")
    else:
        relative = Path(f"assets/clips/{state}/{source.name}")
    return frame_id, relative


def publish_candidates(
    candidate_root: Path,
    public_root: Path,
    approvals: Mapping[str, str],
) -> PublishResult:
    if set(approvals) != set(CLIP_ORDER):
        raise PublishError("publication requires exactly six approved clips")
    reports = {
        clip_id: _load_verified_report(
            candidate_root,
            clip_id,
            approvals[clip_id],
        )
        for clip_id in CLIP_ORDER
    }
    if public_root.exists() and any(public_root.iterdir()):
        raise PublishError(f"public root is not empty: {public_root}")

    public_root.mkdir(parents=True, exist_ok=True)
    frames: dict[str, dict[str, str]] = {}
    clips: dict[str, dict[str, object]] = {}
    for clip_id in CLIP_ORDER:
        report = reports[clip_id]
        state = str(report["state"])
        raw_paths = report.get("frames")
        if not isinstance(raw_paths, list) or len(raw_paths) < 3:
            raise PublishError(f"{clip_id}: report has no playable frames")
        frame_ids: list[str] = []
        for raw_path in raw_paths:
            if not isinstance(raw_path, str):
                raise PublishError(f"{clip_id}: frame path is invalid")
            source = _inside(candidate_root, candidate_root / raw_path)
            if not source.is_file():
                raise PublishError(f"{clip_id}: candidate frame is missing")
            frame_id, relative = _frame_destination(state, source)
            destination = public_root / relative
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            existing = frames.get(frame_id)
            definition = {"src": relative.as_posix(), "sha256": digest}
            if existing is not None and existing != definition:
                raise PublishError(f"{frame_id}: frame ID collision")
            frames[frame_id] = definition
            frame_ids.append(frame_id)
        clips[clip_id] = {
            "state": state,
            "fps": 12,
            "loop": True,
            "quality_status": "approved",
            "frames": frame_ids,
        }

    payload = {
        "version": "4.0",
        "character": "Henry",
        "viewport": {
            "width": 512,
            "height": 512,
            "anchor_x": 0.5,
            "anchor_y": 0.92,
        },
        "transition_frame_id": "henry_s0",
        "frames": frames,
        "clips": clips,
    }
    manifest_path = public_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    validate_manifest(load_manifest(manifest_path), public_root)
    return PublishResult(published=CLIP_ORDER, manifest_path=manifest_path)
