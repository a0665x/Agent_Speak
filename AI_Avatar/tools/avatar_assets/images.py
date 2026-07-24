from __future__ import annotations

from collections import deque
from collections.abc import Iterable

import numpy as np
import cv2
from PIL import Image

from .inventory import Box


def crop_source(sheet: Image.Image, box: Box) -> Image.Image:
    return sheet.convert("RGBA").crop(box)


def remove_border_background(image: Image.Image, tolerance: int) -> Image.Image:
    if tolerance < 0:
        raise ValueError("background tolerance cannot be negative")
    rgba = np.asarray(image.convert("RGBA")).copy()
    rgb = rgba[:, :, :3].astype(np.int16)
    minimum = rgb.min(axis=2)
    chroma = rgb.max(axis=2) - minimum
    background_candidate = np.logical_and(
        minimum >= max(150, 210 - tolerance * 2),
        chroma <= 40 + tolerance * 2,
    )
    height, width = background_candidate.shape
    background = np.zeros_like(background_candidate, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        if background_candidate[0, x]:
            queue.append((x, 0))
        if background_candidate[height - 1, x]:
            queue.append((x, height - 1))
    for y in range(height):
        if background_candidate[y, 0]:
            queue.append((0, y))
        if background_candidate[y, width - 1]:
            queue.append((width - 1, y))
    while queue:
        x, y = queue.popleft()
        if background[y, x] or not background_candidate[y, x]:
            continue
        background[y, x] = True
        queue.extend(_neighbors(x, y, width, height))
    rgba[:, :, 3] = np.where(background, 0, rgba[:, :, 3])
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


def segment_character(
    image: Image.Image,
    *,
    background_tolerance: int = 18,
    iterations: int = 8,
) -> Image.Image:
    if background_tolerance < 0:
        raise ValueError("background tolerance cannot be negative")
    if iterations <= 0:
        raise ValueError("segmentation iterations must be positive")
    rgba = np.asarray(image.convert("RGBA")).copy()
    rgb = rgba[:, :, :3]
    height, width = rgb.shape[:2]
    if height < 8 or width < 8:
        raise ValueError("character source is too small to segment")
    margin = max(2, min(height, width) // 30)
    mask = np.full((height, width), cv2.GC_PR_BGD, dtype=np.uint8)
    mask[margin : height - margin, margin : width - margin] = cv2.GC_PR_FGD
    mask[:margin, :] = cv2.GC_BGD
    mask[height - margin :, :] = cv2.GC_BGD
    mask[:, :margin] = cv2.GC_BGD
    mask[:, width - margin :] = cv2.GC_BGD

    values = rgb.astype(np.int16)
    minimum = values.min(axis=2)
    chroma = values.max(axis=2) - minimum
    strong_foreground = np.logical_or(
        minimum < max(120, 210 - background_tolerance * 2),
        chroma > 40 + background_tolerance * 2,
    )
    inner = np.zeros((height, width), dtype=bool)
    inner[margin : height - margin, margin : width - margin] = True
    mask[np.logical_and(strong_foreground, inner)] = cv2.GC_FGD

    background_model = np.zeros((1, 65), dtype=np.float64)
    foreground_model = np.zeros((1, 65), dtype=np.float64)
    cv2.setRNGSeed(0)
    cv2.grabCut(
        cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
        mask,
        None,
        background_model,
        foreground_model,
        iterations,
        cv2.GC_INIT_WITH_MASK,
    )
    foreground = np.logical_or(mask == cv2.GC_FGD, mask == cv2.GC_PR_FGD)
    rgba[:, :, 3] = np.where(foreground, rgba[:, :, 3], 0)
    return retain_largest_component(Image.fromarray(rgba, "RGBA"))


def normalize_frame(
    image: Image.Image,
    canvas_size: tuple[int, int],
    anchor: tuple[float, float],
    background_tolerance: int,
    reference_width: int,
    reference_height: int | None = None,
) -> Image.Image:
    canvas_width, canvas_height = canvas_size
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError("canvas dimensions must be positive")
    if reference_width <= 0:
        raise ValueError("reference width must be positive")
    if reference_height is not None and reference_height <= 0:
        raise ValueError("reference height must be positive")
    if not 0 <= anchor[0] <= 1 or not 0 <= anchor[1] <= 1:
        raise ValueError("anchor values must be between zero and one")

    foreground = segment_character(
        image,
        background_tolerance=background_tolerance,
    )
    bounds = foreground.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("frame contains no foreground")
    character = foreground.crop(bounds)
    scale = (
        reference_height / character.height
        if reference_height is not None
        else reference_width / character.width
    )
    scale = min(scale, reference_width / character.width)
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
