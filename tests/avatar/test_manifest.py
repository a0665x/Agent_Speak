import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from AI_Avatar.tools.avatar_assets.manifest import (
    ManifestError,
    load_manifest,
    parse_manifest,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "AI_Avatar/config/animation_manifest.json"


def _write_png(path: Path, color: tuple[int, int, int, int]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (512, 512), color).save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_payload(public_root: Path) -> dict[str, object]:
    s0_hash = _write_png(
        public_root / "assets/clips/shared/henry_s0.png",
        (20, 30, 40, 255),
    )
    idle_hash = _write_png(
        public_root / "assets/clips/idle/idle_001.png",
        (30, 40, 50, 255),
    )
    states = ("idle", "listening", "thinking", "speaking", "happy", "error")
    clips = {
        f"{state}_loop": {
            "state": state,
            "fps": 12,
            "loop": True,
            "quality_status": "approved",
            "frames": ["henry_s0", "idle_001", "henry_s0"],
        }
        for state in states
    }
    return {
        "version": "4.0",
        "character": "Henry",
        "viewport": {
            "width": 512,
            "height": 512,
            "anchor_x": 0.5,
            "anchor_y": 0.92,
        },
        "transition_frame_id": "henry_s0",
        "frames": {
            "henry_s0": {
                "src": "assets/clips/shared/henry_s0.png",
                "sha256": s0_hash,
            },
            "idle_001": {
                "src": "assets/clips/idle/idle_001.png",
                "sha256": idle_hash,
            },
        },
        "clips": clips,
    }


def test_every_clip_references_the_same_s0_at_both_boundaries() -> None:
    manifest = load_manifest(MANIFEST_PATH)

    assert manifest.transition_frame_id == "henry_s0"
    assert len(manifest.clips) == 6
    for clip in manifest.clips.values():
        assert clip.loop is True
        assert clip.frames[0] == "henry_s0"
        assert clip.frames[-1] == "henry_s0"


def test_validator_rejects_a_visually_different_tail(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    clips = payload["clips"]
    assert isinstance(clips, dict)
    idle = clips["idle_loop"]
    assert isinstance(idle, dict)
    idle["frames"] = ["henry_s0", "idle_001", "idle_001"]

    with pytest.raises(ManifestError, match="shared transition frame"):
        validate_manifest(parse_manifest(payload), tmp_path)


def test_validator_accepts_approved_shared_s0_manifest(tmp_path: Path) -> None:
    manifest = parse_manifest(_valid_payload(tmp_path))

    validate_manifest(manifest, tmp_path)


def test_validator_rejects_clip_that_is_not_approved(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    clips = payload["clips"]
    assert isinstance(clips, dict)
    idle = clips["idle_loop"]
    assert isinstance(idle, dict)
    idle["quality_status"] = "needs_keyframe"

    with pytest.raises(ManifestError, match="clip is not approved"):
        validate_manifest(parse_manifest(payload), tmp_path)


def test_validator_rejects_path_traversal(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    frames = payload["frames"]
    assert isinstance(frames, dict)
    s0 = frames["henry_s0"]
    assert isinstance(s0, dict)
    s0["src"] = "../private.png"

    with pytest.raises(ManifestError, match="must stay below public root"):
        validate_manifest(parse_manifest(payload), tmp_path)


def test_manifest_schema_is_strict_json() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert payload["version"] == "4.0"
    assert set(payload["clips"]) == {
        "idle_loop",
        "listening_loop",
        "thinking_loop",
        "speaking_loop",
        "happy_loop",
        "error_loop",
    }
