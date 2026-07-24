from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping

from PIL import Image


MVP_STATES = frozenset(
    {"idle", "listening", "thinking", "speaking", "happy", "error"}
)
QualityStatus = Literal["approved", "needs_review", "needs_keyframe"]


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Viewport:
    width: int
    height: int
    anchor_x: float
    anchor_y: float


@dataclass(frozen=True)
class FrameDefinition:
    src: str
    sha256: str | None


@dataclass(frozen=True)
class ClipDefinition:
    state: str
    fps: int
    loop: bool
    quality_status: QualityStatus
    frames: tuple[str, ...]


@dataclass(frozen=True)
class AnimationManifest:
    version: str
    character: str
    viewport: Viewport
    transition_frame_id: str
    frames: Mapping[str, FrameDefinition]
    clips: Mapping[str, ClipDefinition]


def _require_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object")
    return value


def parse_manifest(payload: object) -> AnimationManifest:
    root = _require_mapping(payload, "manifest")
    if root.get("version") != "4.0":
        raise ManifestError("manifest version must be 4.0")
    if root.get("character") != "Henry":
        raise ManifestError("manifest character must be Henry")
    viewport_payload = _require_mapping(root.get("viewport"), "viewport")
    width = viewport_payload.get("width")
    height = viewport_payload.get("height")
    anchor_x = viewport_payload.get("anchor_x")
    anchor_y = viewport_payload.get("anchor_y")
    if (
        not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ManifestError("viewport dimensions must be positive integers")
    if (
        not isinstance(anchor_x, (int, float))
        or not isinstance(anchor_y, (int, float))
        or not 0 <= anchor_x <= 1
        or not 0 <= anchor_y <= 1
    ):
        raise ManifestError("viewport anchors must be between zero and one")

    transition_frame_id = root.get("transition_frame_id")
    if not isinstance(transition_frame_id, str) or not transition_frame_id:
        raise ManifestError("transition_frame_id must be a non-empty string")

    frames_payload = _require_mapping(root.get("frames"), "frames")
    frames: dict[str, FrameDefinition] = {}
    for frame_id, raw_frame in frames_payload.items():
        frame = _require_mapping(raw_frame, f"frames.{frame_id}")
        src = frame.get("src")
        sha256 = frame.get("sha256")
        if not isinstance(src, str) or not src:
            raise ManifestError(f"frames.{frame_id}.src must be a non-empty string")
        if sha256 is not None and (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
        ):
            raise ManifestError(f"frames.{frame_id}.sha256 must be lowercase SHA-256")
        frames[frame_id] = FrameDefinition(src=src, sha256=sha256)
    if transition_frame_id not in frames:
        raise ManifestError("transition frame is missing from frames")

    clips_payload = _require_mapping(root.get("clips"), "clips")
    clips: dict[str, ClipDefinition] = {}
    states: set[str] = set()
    for clip_id, raw_clip in clips_payload.items():
        clip = _require_mapping(raw_clip, f"clips.{clip_id}")
        state = clip.get("state")
        fps = clip.get("fps")
        loop = clip.get("loop")
        quality_status = clip.get("quality_status")
        frame_ids = clip.get("frames")
        if not isinstance(state, str) or state not in MVP_STATES:
            raise ManifestError(f"clips.{clip_id}.state is not an MVP state")
        if not isinstance(fps, int) or fps <= 0:
            raise ManifestError(f"clips.{clip_id}.fps must be a positive integer")
        if loop is not True:
            raise ManifestError(f"clips.{clip_id}.loop must be true")
        if quality_status not in {"approved", "needs_review", "needs_keyframe"}:
            raise ManifestError(f"clips.{clip_id}.quality_status is invalid")
        if (
            not isinstance(frame_ids, list)
            or len(frame_ids) < 3
            or any(not isinstance(frame_id, str) for frame_id in frame_ids)
        ):
            raise ManifestError(f"clips.{clip_id}.frames must contain frame IDs")
        states.add(state)
        clips[clip_id] = ClipDefinition(
            state=state,
            fps=fps,
            loop=True,
            quality_status=quality_status,
            frames=tuple(frame_ids),
        )
    if states != MVP_STATES or len(clips) != len(MVP_STATES):
        raise ManifestError("clips must contain exactly one clip per MVP state")

    return AnimationManifest(
        version="4.0",
        character="Henry",
        viewport=Viewport(width, height, float(anchor_x), float(anchor_y)),
        transition_frame_id=transition_frame_id,
        frames=MappingProxyType(frames),
        clips=MappingProxyType(clips),
    )


def load_manifest(path: Path) -> AnimationManifest:
    return parse_manifest(json.loads(path.read_text(encoding="utf-8")))


def validate_manifest(manifest: AnimationManifest, public_root: Path) -> None:
    root = public_root.resolve()
    for clip_id, clip in manifest.clips.items():
        if (
            clip.frames[0] != manifest.transition_frame_id
            or clip.frames[-1] != manifest.transition_frame_id
        ):
            raise ManifestError(f"{clip_id}: shared transition frame required")
        if clip.quality_status != "approved":
            raise ManifestError(f"{clip_id}: clip is not approved")
        for frame_id in clip.frames:
            if frame_id not in manifest.frames:
                raise ManifestError(f"{clip_id}: unknown frame ID {frame_id}")

    checked: set[str] = set()
    for clip in manifest.clips.values():
        for frame_id in clip.frames:
            if frame_id in checked:
                continue
            checked.add(frame_id)
            definition = manifest.frames[frame_id]
            path = (root / definition.src).resolve()
            if not path.is_relative_to(root):
                raise ManifestError(f"{frame_id}: frame path must stay below public root")
            if not path.is_file():
                raise ManifestError(f"{frame_id}: frame file does not exist")
            if definition.sha256 is None:
                raise ManifestError(f"{frame_id}: approved frame requires SHA-256")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != definition.sha256:
                raise ManifestError(f"{frame_id}: frame SHA-256 mismatch")
            with Image.open(path) as image:
                if image.size != (manifest.viewport.width, manifest.viewport.height):
                    raise ManifestError(f"{frame_id}: frame dimensions do not match viewport")
                if image.mode != "RGBA":
                    raise ManifestError(f"{frame_id}: frame must use RGBA mode")
