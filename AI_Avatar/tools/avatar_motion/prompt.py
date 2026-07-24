from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class PromptImage:
    role: str
    path: Path


@dataclass(frozen=True)
class PromptPacket:
    text: str
    images: tuple[PromptImage, ...]
    identity_invariants: tuple[str, ...]
    geometry_invariants: tuple[str, ...]
    canvas: tuple[int, int]
    background: str


def _required_path(path: Path, label: str) -> Path:
    if str(path) in {"", "."}:
        raise ValueError(f"{label} path is required")
    return path


def build_prompt_packet(
    *,
    canonical_reference: Path,
    current_pose_map: Path,
    nearest_approved_frame: Path,
    identity_invariants: tuple[str, ...],
    geometry_invariants: tuple[str, ...],
    canvas: tuple[int, int],
    background: str,
) -> PromptPacket:
    if canvas[0] <= 0 or canvas[1] <= 0:
        raise ValueError("canvas dimensions must be positive")
    if not HEX_COLOR.fullmatch(background):
        raise ValueError("background must be #RRGGBB")
    images = (
        PromptImage(
            "canonical_reference",
            _required_path(canonical_reference, "canonical reference"),
        ),
        PromptImage(
            "current_pose_map",
            _required_path(current_pose_map, "current pose map"),
        ),
        PromptImage(
            "nearest_approved_frame",
            _required_path(nearest_approved_frame, "nearest approved frame"),
        ),
    )
    identity = "\n".join(f"- {value}" for value in identity_invariants)
    geometry = "\n".join(f"- {value}" for value in geometry_invariants)
    text = (
        "Edit the same full-body character into the pose shown by image 2. "
        "Image 1 is the canonical identity reference. Image 3 is the nearest "
        "approved temporal neighbor. The skeleton is a visual pose instruction, "
        "not ControlNet. Preserve the exact character identity and framing.\n"
        f"Identity invariants:\n{identity or '- preserve every identity detail'}\n"
        f"Geometry invariants:\n{geometry or '- preserve canvas and ground anchor'}\n"
        f"Render on one perfectly flat {background} background with no shadows, "
        f"text, props, scenery, or gradients. Canvas: {canvas[0]}x{canvas[1]}."
    )
    return PromptPacket(
        text=text,
        images=images,
        identity_invariants=identity_invariants,
        geometry_invariants=geometry_invariants,
        canvas=canvas,
        background=background.lower(),
    )

