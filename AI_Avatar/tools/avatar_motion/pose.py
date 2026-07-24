from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from PIL import Image, ImageDraw

from .models import Point, Pose, Rig


BONE_COLOR = (72, 190, 255, 255)
JOINT_COLOR = (255, 113, 214, 255)
LOCKED_COLOR = (255, 201, 74, 255)
BACKGROUND = (10, 15, 27, 255)


def _pixel(point: Point, width: int, height: int) -> tuple[int, int]:
    return (
        round(point.x * (width - 1)),
        round(point.y * (height - 1)),
    )


def resolve_pose_points(rig: Rig, pose: Pose) -> Mapping[str, Point]:
    points = dict(rig.joints)
    for joint_id, point in pose.joints.items():
        if joint_id in rig.locked_joints:
            raise ValueError(f"pose cannot override locked joint: {joint_id}")
        if joint_id not in points:
            raise ValueError(f"pose references unknown joint: {joint_id}")
        points[joint_id] = point
    return MappingProxyType(points)


def render_pose_map_with_points(
    rig: Rig,
    pose: Pose,
) -> tuple[Image.Image, Mapping[str, Point]]:
    width = rig.canvas.width
    height = rig.canvas.height
    points = resolve_pose_points(rig, pose)
    image = Image.new("RGBA", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    bone_width = max(2, round(min(width, height) / 128))
    joint_radius = max(3, round(min(width, height) / 96))
    for start_id, end_id in rig.bones:
        draw.line(
            (
                _pixel(points[start_id], width, height),
                _pixel(points[end_id], width, height),
            ),
            fill=BONE_COLOR,
            width=bone_width,
        )
    for joint_id in sorted(points):
        x, y = _pixel(points[joint_id], width, height)
        color = LOCKED_COLOR if joint_id in rig.locked_joints else JOINT_COLOR
        draw.ellipse(
            (
                x - joint_radius,
                y - joint_radius,
                x + joint_radius,
                y + joint_radius,
            ),
            fill=color,
        )
    return image, points


def render_pose_map(rig: Rig, pose: Pose) -> Image.Image:
    image, _points = render_pose_map_with_points(rig, pose)
    return image


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=False, compress_level=9)

