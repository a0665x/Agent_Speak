from __future__ import annotations

from collections import deque
from collections.abc import Iterable

import numpy as np
from PIL import Image

from .inventory import Box


def crop_source(sheet: Image.Image, box: Box) -> Image.Image:
    return sheet.convert("RGBA").crop(box)


def remove_border_background(image: Image.Image, tolerance: int) -> Image.Image:
    if tolerance < 0:
        raise ValueError("background tolerance cannot be negative")
    rgba = np.asarray(image.convert("RGBA")).copy()
    border = np.concatenate((rgba[0], rgba[-1], rgba[:, 0], rgba[:, -1]))
    background = np.median(border[:, :3], axis=0)
    distance = np.max(
        np.abs(rgba[:, :, :3].astype(np.int16) - background.astype(np.int16)),
        axis=2,
    )
    rgba[:, :, 3] = np.where(distance <= tolerance, 0, rgba[:, :, 3])
    return Image.fromarray(rgba, "RGBA")


def _neighbors(x: int, y: int, width: int, height: int) -> Iterable[tuple[int, int]]:
    if x:
        yield x - 1, y
    if x + 1 < width:
        yield x + 1, y
    if y:
        yield x, y - 1
    if y + 1 < height:
        yield x, y + 1


def retain_largest_component(image: Image.Image) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA")).copy()
    mask = rgba[:, :, 3] > 0
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    largest: list[tuple[int, int]] = []
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue
            component: list[tuple[int, int]] = []
            queue = deque([(x, y)])
            visited[y, x] = True
            while queue:
                current_x, current_y = queue.popleft()
                component.append((current_x, current_y))
                for next_x, next_y in _neighbors(
                    current_x, current_y, width, height
                ):
                    if mask[next_y, next_x] and not visited[next_y, next_x]:
                        visited[next_y, next_x] = True
                        queue.append((next_x, next_y))
            if len(component) > len(largest):
                largest = component
    if not largest:
        raise ValueError("frame contains no foreground")
    keep = np.zeros_like(mask, dtype=bool)
    for x, y in largest:
        keep[y, x] = True
    rgba[:, :, 3] = np.where(keep, rgba[:, :, 3], 0)
    return Image.fromarray(rgba, "RGBA")


def normalize_frame(
    image: Image.Image,
    canvas_size: tuple[int, int],
    anchor: tuple[float, float],
    background_tolerance: int,
    reference_width: int,
) -> Image.Image:
    canvas_width, canvas_height = canvas_size
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError("canvas dimensions must be positive")
    if reference_width <= 0:
        raise ValueError("reference width must be positive")
    if not 0 <= anchor[0] <= 1 or not 0 <= anchor[1] <= 1:
        raise ValueError("anchor values must be between zero and one")

    foreground = retain_largest_component(
        remove_border_background(image, background_tolerance)
    )
    bounds = foreground.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("frame contains no foreground")
    character = foreground.crop(bounds)
    scale = reference_width / character.width
    max_height = max(1, round(canvas_height * anchor[1]))
    scale = min(scale, max_height / character.height)
    target_size = (
        max(1, round(character.width * scale)),
        max(1, round(character.height * scale)),
    )
    if target_size != character.size:
        character = character.resize(target_size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x = round(canvas_width * anchor[0] - character.width / 2)
    y = round(canvas_height * anchor[1] - character.height)
    canvas.alpha_composite(character, (x, y))
    return canvas
