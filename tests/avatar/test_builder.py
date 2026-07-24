import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from AI_Avatar.tools.avatar_assets.builder import (
    assemble_candidate_loop,
    extract_inventory,
    review_candidate_loops,
    write_contact_sheet,
)
from AI_Avatar.tools.build_avatar_assets import main


ROOT = Path(__file__).resolve().parents[2]


def _sheet(path: Path) -> None:
    image = Image.new("RGBA", (120, 120), "white")
    ImageDraw.Draw(image).rounded_rectangle(
        (35, 15, 84, 104),
        radius=12,
        fill=(70, 90, 110, 255),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _inventory(tmp_path: Path) -> tuple[Path, Path]:
    sheets = tmp_path / "sheets"
    _sheet(sheets / "sheet.png")
    payload = {
        "version": "1.0",
        "character": "Henry",
        "composition": "waist_up",
        "canvas": {
            "width": 512,
            "height": 512,
            "anchor_x": 0.5,
            "anchor_y": 0.92,
        },
        "transition_source": {
            "sheet": "sheet.png",
            "boxes": [[0, 0, 120, 120]],
        },
        "states": {
            state: {
                "sheet": "sheet.png",
                "boxes": [[0, 0, 120, 120]],
            }
            for state in (
                "idle",
                "listening",
                "thinking",
                "speaking",
                "happy",
                "error",
            )
        },
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, sheets


def test_extract_inventory_writes_normalized_s0_and_core_frames(
    tmp_path: Path,
) -> None:
    inventory, sheets = _inventory(tmp_path)
    candidates = tmp_path / "candidates"

    result = extract_inventory(
        inventory,
        sheets,
        candidates,
        reference_width=300,
        background_tolerance=12,
    )

    assert result.transition_frame == candidates / "shared/henry_s0.png"
    assert result.states["idle"] == (
        candidates / "extracted/idle/idle_001.png",
    )
    with Image.open(result.transition_frame) as frame:
        assert frame.mode == "RGBA"
        assert frame.size == (512, 512)
        assert frame.getchannel("A").getbbox() is not None


def test_assemble_candidate_loop_inserts_entry_and_exit_frames(
    tmp_path: Path,
) -> None:
    s0 = tmp_path / "henry_s0.png"
    core = tmp_path / "idle_001.png"
    entry = tmp_path / "idle_entry_001.png"
    exit_frame = tmp_path / "idle_exit_001.png"
    for path in (s0, core, entry, exit_frame):
        Image.new("RGBA", (512, 512), (20, 30, 40, 255)).save(path)

    def interpolate(start: Path, end: Path, phase: str) -> tuple[Path, ...]:
        assert start.is_file() and end.is_file()
        return (entry,) if phase == "entry" else (exit_frame,)

    frames = assemble_candidate_loop(s0, (core,), interpolate)

    assert frames == (s0, entry, core, exit_frame, s0)


def test_assemble_candidate_loop_interpolates_each_core_keyframe_pair(
    tmp_path: Path,
) -> None:
    paths = {
        name: tmp_path / f"{name}.png"
        for name in ("s0", "core1", "core2", "entry", "between", "exit")
    }
    for index, path in enumerate(paths.values()):
        Image.new("RGBA", (32, 32), (index, 20, 30, 255)).save(path)
    phases: list[str] = []

    def interpolate(_start: Path, _end: Path, phase: str) -> tuple[Path, ...]:
        phases.append(phase)
        return {
            "entry": (paths["entry"],),
            "core_001": (paths["between"],),
            "exit": (paths["exit"],),
        }[phase]

    frames = assemble_candidate_loop(
        paths["s0"],
        (paths["core1"], paths["core2"]),
        interpolate,
    )

    assert phases == ["entry", "core_001", "exit"]
    assert frames == (
        paths["s0"],
        paths["entry"],
        paths["core1"],
        paths["between"],
        paths["core2"],
        paths["exit"],
        paths["s0"],
    )


def test_review_candidate_loops_writes_reports_and_previews(tmp_path: Path) -> None:
    inventory, sheets = _inventory(tmp_path)
    candidates = tmp_path / "candidates"
    extracted = extract_inventory(inventory, sheets, candidates)
    labels: list[str] = []

    def no_interpolation(
        _start: Path,
        _end: Path,
        label: str,
    ) -> tuple[Path, ...]:
        labels.append(label)
        return ()

    result = review_candidate_loops(
        extracted,
        candidates,
        interpolator=no_interpolation,
    )

    assert set(result.report_hashes) == {
        "idle_loop",
        "listening_loop",
        "thinking_loop",
        "speaking_loop",
        "happy_loop",
        "error_loop",
    }
    assert labels[:2] == ["idle_entry", "idle_exit"]
    assert labels[-2:] == ["error_entry", "error_exit"]
    assert (candidates / "clips/idle/report.json").is_file()
    assert (candidates / "previews/idle_loop.gif").is_file()


def test_cli_extract_reports_candidate_location(
    tmp_path: Path,
    capsys,
) -> None:
    inventory, sheets = _inventory(tmp_path)
    candidates = tmp_path / "candidates"

    exit_code = main(
        [
            "extract",
            "--inventory",
            str(inventory),
            "--sheets",
            str(sheets),
            "--candidates",
            str(candidates),
        ]
    )

    assert exit_code == 0
    assert (
        capsys.readouterr().out.strip()
        == f"AVATAR_EXTRACTED states=6 candidates={candidates}"
    )


def test_build_script_supports_direct_cli_invocation() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "AI_Avatar/tools/build_avatar_assets.py"),
            "--help",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Inspect, build, review, and publish" in result.stdout


def test_setup_script_reuses_an_already_pinned_checkout_offline() -> None:
    source = (
        ROOT / "AI_Avatar/tools/setup_interpolation_models.sh"
    ).read_text(encoding="utf-8")

    assert 'current_commit=$(git -C "$target" rev-parse HEAD)' in source
    assert 'if [[ "$current_commit" != "$commit" ]]; then' in source


def test_cli_review_publish_and_validate_flow(tmp_path: Path, capsys) -> None:
    inventory, sheets = _inventory(tmp_path)
    candidates = tmp_path / "candidates"
    public = tmp_path / "public"
    main(
        [
            "extract",
            "--inventory",
            str(inventory),
            "--sheets",
            str(sheets),
            "--candidates",
            str(candidates),
        ]
    )
    capsys.readouterr()

    assert (
        main(
            [
                "review",
                "--candidates",
                str(candidates),
                "--provider",
                "none",
            ]
        )
        == 0
    )
    assert "AVATAR_REVIEW_READY clips=6" in capsys.readouterr().out
    approvals = []
    for state in ("idle", "listening", "thinking", "speaking", "happy", "error"):
        report = json.loads(
            (candidates / f"clips/{state}/report.json").read_text(encoding="utf-8")
        )
        approvals.extend(
            ["--approve", f"{state}_loop:{report['report_sha256']}"]
        )

    assert (
        main(
            [
                "publish",
                "--candidates",
                str(candidates),
                "--public",
                str(public),
                *approvals,
            ]
        )
        == 0
    )
    assert "AVATAR_PUBLISHED clips=6" in capsys.readouterr().out

    assert main(["validate", "--public", str(public)]) == 0
    assert (
        capsys.readouterr().out.strip()
        == "AVATAR_ASSETS_VALID clips=6 transition=henry_s0"
    )


def test_cli_review_uses_requested_model_provider(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    inventory, sheets = _inventory(tmp_path)
    candidates = tmp_path / "candidates"
    main(
        [
            "extract",
            "--inventory",
            str(inventory),
            "--sheets",
            str(sheets),
            "--candidates",
            str(candidates),
        ]
    )
    capsys.readouterr()
    requested: list[str] = []

    def fake_builder(
        _config: Path,
        *,
        project_root: Path,
        candidate_root: Path,
        preferred: str,
    ):
        assert project_root.is_dir()
        assert candidate_root == candidates
        requested.append(preferred)
        return lambda _start, _end, _label: ()

    monkeypatch.setattr(
        "AI_Avatar.tools.build_avatar_assets.build_routed_interpolator",
        fake_builder,
    )

    assert (
        main(
            [
                "review",
                "--candidates",
                str(candidates),
                "--provider",
                "film",
            ]
        )
        == 0
    )
    assert requested == ["film"]


def test_write_contact_sheet_includes_s0_and_six_states(tmp_path: Path) -> None:
    inventory, sheets = _inventory(tmp_path)
    extracted = extract_inventory(inventory, sheets, tmp_path / "candidates")
    output = tmp_path / "review/contact-sheet.png"

    count = write_contact_sheet(extracted, output)

    assert count == 7
    with Image.open(output) as contact:
        assert contact.mode == "RGBA"
        assert contact.width > contact.height


def test_cli_inspect_writes_contact_sheet(tmp_path: Path, capsys) -> None:
    inventory, sheets = _inventory(tmp_path)
    candidates = tmp_path / "candidates"
    output = tmp_path / "review/contact-sheet.png"

    assert (
        main(
            [
                "inspect",
                "--inventory",
                str(inventory),
                "--sheets",
                str(sheets),
                "--candidates",
                str(candidates),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert output.is_file()
    assert (
        capsys.readouterr().out.strip()
        == f"AVATAR_INVENTORY_READY entries=7 contact_sheet={output}"
    )
