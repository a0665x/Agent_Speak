from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class ChromaKey:
    color: str
    tolerance: int
    feather_radius: int

    def __post_init__(self) -> None:
        if not HEX_COLOR.fullmatch(self.color):
            raise ValueError("color must be #RRGGBB")
        if not 0 <= self.tolerance <= 255:
            raise ValueError("tolerance must be between 0 and 255")
        if not 0 <= self.feather_radius <= 16:
            raise ValueError("feather radius must be between 0 and 16")

    @property
    def rgb(self) -> np.ndarray:
        return np.array(
            [int(self.color[index : index + 2], 16) for index in (1, 3, 5)],
            dtype=np.int16,
        )


def chroma_to_rgba(image: Image.Image, key: ChromaKey) -> Image.Image:
    rgb = np.asarray(image.convert("RGB")).astype(np.int16)
    distance = np.linalg.norm(rgb - key.rgb, axis=2)
    foreground = (distance > key.tolerance).astype(np.uint8) * 255
    if key.feather_radius:
        kernel = key.feather_radius * 2 + 1
        feathered = cv2.GaussianBlur(foreground, (kernel, kernel), 0)
        foreground = np.maximum(foreground, feathered)
    rgba = np.empty((*foreground.shape, 4), dtype=np.uint8)
    rgba[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = foreground

    edge = np.logical_and(foreground > 0, foreground < 255)
    if np.any(edge):
        red = rgba[:, :, 0]
        green = rgba[:, :, 1]
        blue = rgba[:, :, 2]
        green[edge] = np.minimum(
            green[edge],
            np.maximum(red[edge], blue[edge]) + 12,
        )
    rgba[foreground == 0, :3] = 0
    return Image.fromarray(rgba, "RGBA")
