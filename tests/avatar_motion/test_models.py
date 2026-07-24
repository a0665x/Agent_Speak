from __future__ import annotations

import json
from pathlib import Path

import pytest

from AI_Avatar.tools.avatar_motion.models import (
    load_candidate_clip,
    load_motion,
    load_rig,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _rig_payload() -> dict:
    return {
        "version": "1.0",
        "character_id": "henry",
        "review_status": "approved",
        "canvas": {
            "width": 512,
            "height": 512,
            "anchor_x": 0.5,
            "anchor_y": 0.92,
        },
        "joints": {
            "ear_root_left": {"x": 0.42, "y": 0.18},
            "ear_tip_left": {"x": 0.40, "y": 0.08},
            "hip": {"x": 0.50, "y": 0.68},
            "foot_left": {"x": 0.43, "y": 0.92},
            "foot_right": {"x": 0.57, "y": 0.92},
        },
        "bones": [
            ["ear_root_left", "ear_tip_left"],
            ["hip", "foot_left"],
            ["hip", "foot_right"],
        ],
        "locked_joints": ["foot_left", "foot_right"],
        "identity_regions": ["glasses", "badge", "tie"],
        "s0_sha256": "a" * 64,
    }


def _motion_payload() -> dict:
    return {
        "version": "1.0",
        "motion_id": "scratch_head",
        "character_id": "henry",
        "fps": 12,
        "duration_seconds": 3,
        "s0_sha256": "a" * 64,
        "poses": [
            {"id": "s0", "frame": 0, "joints": {}},
            {
                "id": "lift",
                "frame": 8,
                "joints": {"ear_tip_left": {"x": 0.41, "y": 0.09}},
            },
            {"id": "s0", "frame": 36, "joints": {}},
        ],
    }


def _candidate_payload() -> dict:
    return {
        "version": "1.0",
        "source_type": "gpt_image_keyframes",
        "character_id": "henry",
        "motion_id": "scratch_head",
        "transition_frame_id": "S0",
        "transition_frame_sha256": "a" * 64,
        "first_frame_sha256": "a" * 64,
        "last_frame_sha256": "a" * 64,
        "fps": 12,
        "frame_count": 37,
        "canvas": {"width": 512, "height": 512},
        "frames_dir": "frames",
        "preview_media": None,
        "source_metadata": "source.json",
        "approval_record": "approvals.json",
    }


def test_rig_supports_character_specific_extension_joints(tmp_path: Path) -> None:
    rig = load_rig(_write_json(tmp_path / "rig.json", _rig_payload()))

    assert rig.joints["ear_tip_left"].x == 0.40
    assert rig.bones[0] == ("ear_root_left", "ear_tip_left")


def test_rig_rejects_bone_with_unknown_joint(tmp_path: Path) -> None:
    payload = _rig_payload()
    payload["bones"].append(["hip", "tail_tip"])

    with pytest.raises(ValueError, match="unknown joint"):
        load_rig(_write_json(tmp_path / "rig.json", payload))


def test_motion_rejects_unknown_joint(tmp_path: Path) -> None:
    rig = load_rig(_write_json(tmp_path / "rig.json", _rig_payload()))
    payload = _motion_payload()
    payload["poses"][1]["joints"] = {"third_arm": {"x": 0.2, "y": 0.3}}

    with pytest.raises(ValueError, match="unknown joint"):
        load_motion(_write_json(tmp_path / "motion.json", payload), rig)


def test_candidate_contract_requires_exact_s0_hash_at_both_boundaries(
    tmp_path: Path,
) -> None:
    payload = _candidate_payload()
    payload["last_frame_sha256"] = "b" * 64

    with pytest.raises(ValueError, match="boundary"):
        load_candidate_clip(_write_json(tmp_path / "clip.json", payload))


def test_safe_identifiers_reject_path_segments(tmp_path: Path) -> None:
    payload = _rig_payload()
    payload["character_id"] = "../../escape"

    with pytest.raises(ValueError, match="safe identifier"):
        load_rig(_write_json(tmp_path / "rig.json", payload))
