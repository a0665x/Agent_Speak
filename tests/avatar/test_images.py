from PIL import Image, ImageDraw
from pathlib import Path

from AI_Avatar.tools.avatar_assets.images import (
    crop_source,
    normalize_frame,
    remove_border_background,
    retain_largest_component,
    segment_character,
)


def _make_fixture(*, offset_x: int = 0) -> Image.Image:
    source = Image.new("RGBA", (100, 100), "white")
    ImageDraw.Draw(source).rectangle(
        (30 + offset_x, 20, 69 + offset_x, 89),
        fill=(40, 60, 80, 255),
    )
    return source


def test_normalize_places_character_on_fixed_baseline() -> None:
    normalized = normalize_frame(
        _make_fixture(),
        canvas_size=(512, 512),
        anchor=(0.5, 0.92),
        background_tolerance=12,
        reference_width=40,
    )

    alpha_box = normalized.getchannel("A").getbbox()
    assert normalized.size == (512, 512)
    assert alpha_box is not None
    assert alpha_box[3] == round(512 * 0.92)


def test_normalize_centers_character_without_position_drift() -> None:
    first = normalize_frame(
        _make_fixture(offset_x=0),
        canvas_size=(512, 512),
        anchor=(0.5, 0.92),
        background_tolerance=12,
        reference_width=40,
    )
    second = normalize_frame(
        _make_fixture(offset_x=8),
        canvas_size=(512, 512),
        anchor=(0.5, 0.92),
        background_tolerance=12,
        reference_width=40,
    )

    assert first.getchannel("A").getbbox() == second.getchannel("A").getbbox()


def test_largest_component_discards_detached_sheet_label() -> None:
    source = Image.new("RGBA", (100, 100), "white")
    draw = ImageDraw.Draw(source)
    draw.rectangle((25, 20, 74, 89), fill=(30, 40, 50, 255))
    draw.rectangle((2, 2, 10, 10), fill=(120, 80, 160, 255))

    foreground = remove_border_background(source, tolerance=12)
    cleaned = retain_largest_component(foreground)

    assert cleaned.getchannel("A").getbbox() == (25, 20, 75, 90)
    assert cleaned.getpixel((5, 5))[3] == 0


def test_crop_source_uses_inventory_box_without_mutating_sheet() -> None:
    source = Image.new("RGBA", (64, 64), (10, 20, 30, 255))
    cropped = crop_source(source, (10, 12, 30, 42))

    assert cropped.size == (20, 30)
    assert source.size == (64, 64)


def test_status_card_background_and_number_are_removed() -> None:
    root = Path(__file__).resolve().parents[2]
    with Image.open(
        root / "AI_Avatar/assets/sheets/01_loop_core_idle_listening_thinking.png"
    ) as sheet:
        card = crop_source(sheet, (34, 127, 300, 423))

    cleaned = retain_largest_component(
        remove_border_background(card, tolerance=18)
    )
    bounds = cleaned.getchannel("A").getbbox()

    assert bounds is not None
    assert cleaned.getpixel((28, 28))[3] == 0
    assert cleaned.getpixel((0, 0))[3] == 0
    assert bounds[2] < card.width - 8
    assert bounds[3] < card.height - 8


def test_normalize_uses_reference_height_instead_of_gesture_width() -> None:
    narrow = Image.new("RGBA", (120, 120), "white")
    wide = Image.new("RGBA", (120, 120), "white")
    ImageDraw.Draw(narrow).rectangle((45, 20, 74, 99), fill=(30, 40, 50, 255))
    ImageDraw.Draw(wide).rectangle((20, 20, 99, 99), fill=(30, 40, 50, 255))

    narrow_result = normalize_frame(
        narrow,
        canvas_size=(512, 512),
        anchor=(0.5, 0.92),
        background_tolerance=12,
        reference_width=380,
        reference_height=320,
    )
    wide_result = normalize_frame(
        wide,
        canvas_size=(512, 512),
        anchor=(0.5, 0.92),
        background_tolerance=12,
        reference_width=380,
        reference_height=320,
    )

    narrow_box = narrow_result.getchannel("A").getbbox()
    wide_box = wide_result.getchannel("A").getbbox()
    assert narrow_box is not None and wide_box is not None
    assert narrow_box[3] - narrow_box[1] == 320
    assert wide_box[3] - wide_box[1] == 320


def test_character_segmentation_preserves_white_shirt_and_right_sleeve() -> None:
    root = Path(__file__).resolve().parents[2]
    with Image.open(
        root / "AI_Avatar/assets/sheets/04_gesture_keyframes.png"
    ) as sheet:
        source = crop_source(sheet, (18, 230, 159, 430))

    segmented = segment_character(source)

    assert segmented.getpixel((110, 150))[3] > 0
    assert segmented.getpixel((72, 184))[3] > 0
    assert segmented.getpixel((70, 8))[3] == 0
