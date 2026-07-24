from PIL import Image, ImageDraw

from AI_Avatar.tools.avatar_assets.images import (
    crop_source,
    normalize_frame,
    remove_border_background,
    retain_largest_component,
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
