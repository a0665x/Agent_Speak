from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from PIL import Image


MVP_STATES = frozenset(
    {"idle", "listening", "thinking", "speaking", "happy", "error"}
)
Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class FrameSource:
    sheet: str
    boxes: tuple[Box, ...]


@dataclass(frozen=True)
class AssetInventory:
    version: str
    canvas: tuple[int, int]
    anchor: tuple[float, float]
    composition: str
    transition_source: FrameSource
    states: Mapping[str, FrameSource]


def _parse_source(value: object, *, label: str) -> FrameSource:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    sheet = value.get("sheet")
    boxes = value.get("boxes")
    if not isinstance(sheet, str) or not sheet or Path(sheet).name != sheet:
        raise ValueError(f"{label}.sheet must be a local filename")
    if not isinstance(boxes, list) or not boxes:
        raise ValueError(f"{label}.boxes must be a non-empty list")
    parsed_boxes: list[Box] = []
    for index, box in enumerate(boxes):
        if (
            not isinstance(box, list)
            or len(box) != 4
            or any(not isinstance(item, int) for item in box)
        ):
            raise ValueError(f"{label}.boxes[{index}] must contain four integers")
        parsed_boxes.append((box[0], box[1], box[2], box[3]))
    return FrameSource(sheet=sheet, boxes=tuple(parsed_boxes))


def _parse_inventory(payload: object) -> AssetInventory:
    if not isinstance(payload, dict):
        raise ValueError("inventory must be an object")
    canvas = payload.get("canvas")
    if not isinstance(canvas, dict):
        raise ValueError("canvas must be an object")
    width = canvas.get("width")
    height = canvas.get("height")
    anchor_x = canvas.get("anchor_x")
    anchor_y = canvas.get("anchor_y")
    if (
        not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("canvas dimensions must be positive integers")
    if (
        not isinstance(anchor_x, (int, float))
        or not isinstance(anchor_y, (int, float))
        or not 0 <= anchor_x <= 1
        or not 0 <= anchor_y <= 1
    ):
        raise ValueError("canvas anchors must be between zero and one")
    composition = payload.get("composition")
    if composition != "waist_up":
        raise ValueError("composition must be waist_up")
    states_payload = payload.get("states")
    if not isinstance(states_payload, dict) or set(states_payload) != MVP_STATES:
        raise ValueError("states must contain exactly the MVP states")
    states = {
        state: _parse_source(states_payload[state], label=f"states.{state}")
        for state in sorted(MVP_STATES)
    }
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("version must be a non-empty string")
    return AssetInventory(
        version=version,
        canvas=(width, height),
        anchor=(float(anchor_x), float(anchor_y)),
        composition=composition,
        transition_source=_parse_source(
            payload.get("transition_source"), label="transition_source"
        ),
        states=MappingProxyType(states),
    )


def load_inventory(path: Path, sheets_dir: Path) -> AssetInventory:
    inventory = _parse_inventory(json.loads(path.read_text(encoding="utf-8")))
    for source in (inventory.transition_source, *inventory.states.values()):
        image_path = sheets_dir / source.sheet
        if not image_path.is_file():
            raise ValueError(f"source sheet does not exist: {source.sheet}")
        with Image.open(image_path) as image:
            width, height = image.size
        for left, top, right, bottom in source.boxes:
            if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                raise ValueError(f"box outside source bounds: {source.sheet}")
    return inventory
