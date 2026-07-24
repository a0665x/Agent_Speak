from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = (
    PROJECT_ROOT
    / "AI_Avatar/assets/skills/generate-character-motion/assets"
)
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Canvas:
    width: int
    height: int
    anchor_x: float
    anchor_y: float


@dataclass(frozen=True)
class Rig:
    version: str
    character_id: str
    review_status: str
    canvas: Canvas
    joints: Mapping[str, Point]
    bones: tuple[tuple[str, str], ...]
    locked_joints: tuple[str, ...]
    identity_regions: tuple[str, ...]
    s0_sha256: str


@dataclass(frozen=True)
class Pose:
    id: str
    frame: int
    joints: Mapping[str, Point]


@dataclass(frozen=True)
class Motion:
    version: str
    motion_id: str
    character_id: str
    fps: int
    duration_seconds: float
    s0_sha256: str
    poses: tuple[Pose, ...]


@dataclass(frozen=True)
class CandidateClip:
    version: str
    source_type: str
    character_id: str
    motion_id: str
    transition_frame_id: str
    transition_frame_sha256: str
    first_frame_sha256: str
    last_frame_sha256: str
    fps: int
    frame_count: int
    canvas: tuple[int, int]
    frames_dir: str
    preview_media: str | None
    source_metadata: str
    approval_record: str


def _read_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError("JSON document must be an object")
    return payload


def _validate(payload: dict, schema_name: str) -> None:
    schema = _read_payload(SCHEMA_ROOT / schema_name)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(item) for item in error.absolute_path) or "$"
        raise ValueError(f"{location}: {error.message}")


def _safe_id(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError(f"safe identifier required: {value!r}")
    return value


def _point(payload: Mapping[str, object]) -> Point:
    return Point(x=float(payload["x"]), y=float(payload["y"]))


def load_rig(path: Path) -> Rig:
    payload = _read_payload(path)
    _validate(payload, "rig.schema.json")
    character_id = _safe_id(str(payload["character_id"]))
    raw_joints = payload["joints"]
    assert isinstance(raw_joints, dict)
    joints = {
        _safe_id(str(joint_id)): _point(value)
        for joint_id, value in raw_joints.items()
    }
    raw_bones = payload["bones"]
    assert isinstance(raw_bones, list)
    bones = tuple((str(value[0]), str(value[1])) for value in raw_bones)
    for start, end in bones:
        if start not in joints or end not in joints:
            raise ValueError(f"bone references unknown joint: {start}, {end}")
    locked = tuple(str(value) for value in payload["locked_joints"])
    unknown_locked = sorted(set(locked).difference(joints))
    if unknown_locked:
        raise ValueError(f"locked unknown joint: {unknown_locked[0]}")
    canvas = payload["canvas"]
    assert isinstance(canvas, dict)
    return Rig(
        version=str(payload["version"]),
        character_id=character_id,
        review_status=str(payload["review_status"]),
        canvas=Canvas(
            width=int(canvas["width"]),
            height=int(canvas["height"]),
            anchor_x=float(canvas["anchor_x"]),
            anchor_y=float(canvas["anchor_y"]),
        ),
        joints=MappingProxyType(joints),
        bones=bones,
        locked_joints=locked,
        identity_regions=tuple(str(value) for value in payload["identity_regions"]),
        s0_sha256=str(payload["s0_sha256"]),
    )


def load_motion(path: Path, rig: Rig) -> Motion:
    payload = _read_payload(path)
    _validate(payload, "motion.schema.json")
    motion_id = _safe_id(str(payload["motion_id"]))
    character_id = _safe_id(str(payload["character_id"]))
    if character_id != rig.character_id:
        raise ValueError("motion character does not match rig")
    if str(payload["s0_sha256"]) != rig.s0_sha256:
        raise ValueError("motion S0 hash does not match rig")
    poses: list[Pose] = []
    previous_frame = -1
    for raw_pose in payload["poses"]:
        pose_id = _safe_id(str(raw_pose["id"]))
        frame = int(raw_pose["frame"])
        if frame <= previous_frame:
            raise ValueError("pose frames must be strictly increasing")
        previous_frame = frame
        raw_joints = raw_pose["joints"]
        joints = {
            _safe_id(str(joint_id)): _point(value)
            for joint_id, value in raw_joints.items()
        }
        unknown = sorted(set(joints).difference(rig.joints))
        if unknown:
            raise ValueError(f"pose references unknown joint: {unknown[0]}")
        locked = sorted(set(joints).intersection(rig.locked_joints))
        if locked:
            raise ValueError(f"pose overrides locked joint: {locked[0]}")
        poses.append(
            Pose(
                id=pose_id,
                frame=frame,
                joints=MappingProxyType(joints),
            )
        )
    expected_final = round(float(payload["duration_seconds"]) * int(payload["fps"]))
    if poses[0].id != "s0" or poses[0].frame != 0:
        raise ValueError("motion must begin with S0 at frame zero")
    if poses[-1].id != "s0" or poses[-1].frame != expected_final:
        raise ValueError("motion must end with S0 at the duration boundary")
    return Motion(
        version=str(payload["version"]),
        motion_id=motion_id,
        character_id=character_id,
        fps=int(payload["fps"]),
        duration_seconds=float(payload["duration_seconds"]),
        s0_sha256=str(payload["s0_sha256"]),
        poses=tuple(poses),
    )


def load_candidate_clip(path: Path) -> CandidateClip:
    payload = _read_payload(path)
    _validate(payload, "candidate-clip.schema.json")
    transition_hash = str(payload["transition_frame_sha256"])
    first_hash = str(payload["first_frame_sha256"])
    last_hash = str(payload["last_frame_sha256"])
    if first_hash != transition_hash or last_hash != transition_hash:
        raise ValueError("candidate boundary hashes must equal exact S0")
    canvas = payload["canvas"]
    assert isinstance(canvas, dict)
    return CandidateClip(
        version=str(payload["version"]),
        source_type=str(payload["source_type"]),
        character_id=_safe_id(str(payload["character_id"])),
        motion_id=_safe_id(str(payload["motion_id"])),
        transition_frame_id=str(payload["transition_frame_id"]),
        transition_frame_sha256=transition_hash,
        first_frame_sha256=first_hash,
        last_frame_sha256=last_hash,
        fps=int(payload["fps"]),
        frame_count=int(payload["frame_count"]),
        canvas=(int(canvas["width"]), int(canvas["height"])),
        frames_dir=str(payload["frames_dir"]),
        preview_media=(
            None
            if payload["preview_media"] is None
            else str(payload["preview_media"])
        ),
        source_metadata=str(payload["source_metadata"]),
        approval_record=str(payload["approval_record"]),
    )

