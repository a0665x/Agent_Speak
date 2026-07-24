import json
from pathlib import Path

import pytest
from PIL import Image

from AI_Avatar.tools.avatar_assets.inventory import load_inventory


ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = ROOT / "AI_Avatar/config/verified_asset_inventory.json"
SHEETS_DIR = ROOT / "AI_Avatar/assets/sheets"


def test_verified_inventory_maps_all_mvp_states() -> None:
    inventory = load_inventory(INVENTORY_PATH, SHEETS_DIR)

    assert set(inventory.states) == {
        "idle",
        "listening",
        "thinking",
        "speaking",
        "happy",
        "error",
    }
    assert inventory.states["idle"].sheet == "03_reaction_happy_laugh.png"
    assert inventory.states["speaking"].sheet == "04_gesture_keyframes.png"
    assert (
        inventory.transition_source.sheet
        == "01_loop_core_idle_listening_thinking.png"
    )
    assert inventory.composition == "waist_up"
    assert inventory.canvas == (512, 512)


def test_inventory_rejects_a_cell_outside_its_source_image(tmp_path: Path) -> None:
    sheets_dir = tmp_path / "sheets"
    sheets_dir.mkdir()
    Image.new("RGB", (64, 64), "white").save(sheets_dir / "sheet.png")
    invalid = tmp_path / "inventory.json"
    invalid.write_text(
        json.dumps(
            {
                "version": "1.0",
                "canvas": {
                    "width": 512,
                    "height": 512,
                    "anchor_x": 0.5,
                    "anchor_y": 0.92,
                },
                "composition": "waist_up",
                "transition_source": {
                    "sheet": "sheet.png",
                    "boxes": [[0, 0, 999, 999]],
                },
                "states": {
                    state: {"sheet": "sheet.png", "boxes": [[0, 0, 32, 32]]}
                    for state in (
                        "idle",
                        "listening",
                        "thinking",
                        "speaking",
                        "happy",
                        "error",
                    )
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="outside source bounds"):
        load_inventory(invalid, sheets_dir)


def test_inventory_rejects_missing_mvp_state(tmp_path: Path) -> None:
    sheets_dir = tmp_path / "sheets"
    sheets_dir.mkdir()
    Image.new("RGB", (64, 64), "white").save(sheets_dir / "sheet.png")
    payload = {
        "version": "1.0",
        "canvas": {
            "width": 512,
            "height": 512,
            "anchor_x": 0.5,
            "anchor_y": 0.92,
        },
        "composition": "waist_up",
        "transition_source": {
            "sheet": "sheet.png",
            "boxes": [[0, 0, 32, 32]],
        },
        "states": {
            "idle": {"sheet": "sheet.png", "boxes": [[0, 0, 32, 32]]},
        },
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly the MVP states"):
        load_inventory(path, sheets_dir)
