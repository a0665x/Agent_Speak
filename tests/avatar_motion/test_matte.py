from __future__ import annotations

from PIL import Image, ImageDraw

from AI_Avatar.tools.avatar_motion.matte import ChromaKey, chroma_to_rgba


def _green_fixture() -> Image.Image:
    image = Image.new("RGB", (64, 64), (0, 255, 102))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 8, 44, 58), radius=6, fill=(120, 78, 48))
    draw.rectangle((14, 10, 22, 16), fill=(120, 78, 48))
    return image


def test_chroma_matte_keeps_paw_tip_and_removes_green_corners() -> None:
    result = chroma_to_rgba(
        _green_fixture(),
        ChromaKey(color="#00ff66", tolerance=48, feather_radius=1),
    )

    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((14, 12))[3] > 220
    assert result.getpixel((14, 12))[1] < 150


def test_chroma_key_rejects_invalid_configuration() -> None:
    try:
        ChromaKey(color="green", tolerance=-1, feather_radius=1)
    except ValueError as error:
        assert "color" in str(error) or "tolerance" in str(error)
    else:
        raise AssertionError("invalid chroma key was accepted")

