from __future__ import annotations

from types import MappingProxyType

from AI_Avatar.tools.avatar_motion.models import Canvas, Point, Pose, Rig
from AI_Avatar.tools.avatar_motion.pose import (
    render_pose_map,
    render_pose_map_with_points,
    save_png,
)


def _rig() -> Rig:
    return Rig(
        version="1.0",
        character_id="test",
        review_status="approved",
        canvas=Canvas(128, 128, 0.5, 0.92),
        joints=MappingProxyType(
            {
                "hip": Point(0.5, 0.55),
                "paw": Point(0.35, 0.50),
                "foot_left": Point(0.43, 0.92),
                "foot_right": Point(0.57, 0.92),
            }
        ),
        bones=(("hip", "paw"), ("hip", "foot_left"), ("hip", "foot_right")),
        locked_joints=("foot_left", "foot_right"),
        identity_regions=(),
        s0_sha256="a" * 64,
    )


def _pose() -> Pose:
    return Pose(
        id="lift",
        frame=4,
        joints=MappingProxyType({"paw": Point(0.30, 0.35)}),
    )


def test_pose_renderer_is_byte_deterministic(tmp_path) -> None:
    first = render_pose_map(_rig(), _pose())
    second = render_pose_map(_rig(), _pose())
    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"

    save_png(first, first_path)
    save_png(second, second_path)

    assert first_path.read_bytes() == second_path.read_bytes()


def test_locked_feet_remain_at_rig_coordinates() -> None:
    _image, resolved = render_pose_map_with_points(_rig(), _pose())

    assert resolved["foot_left"] == _rig().joints["foot_left"]
    assert resolved["foot_right"] == _rig().joints["foot_right"]
    assert resolved["paw"] == Point(0.30, 0.35)


def test_pose_renderer_uses_exact_canvas() -> None:
    image = render_pose_map(_rig(), _pose())

    assert image.mode == "RGBA"
    assert image.size == (128, 128)

