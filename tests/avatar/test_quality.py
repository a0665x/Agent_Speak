from PIL import Image, ImageDraw

from AI_Avatar.tools.avatar_assets.quality import (
    QualityThresholds,
    assess_sequence,
)


def _pose(
    *,
    x: int = 40,
    y: int = 20,
    width: int = 30,
    height: int = 70,
) -> Image.Image:
    image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle(
        (x, y, x + width - 1, y + height - 1),
        fill=(90, 110, 130, 255),
    )
    return image


def _thresholds() -> QualityThresholds:
    return QualityThresholds(
        max_adjacent_delta=0.18,
        max_alpha_growth=0.25,
        max_center_drift=0.12,
        max_baseline_drift=0.04,
    )


def test_clean_generated_sequence_requires_human_review() -> None:
    report = assess_sequence(
        [_pose(x=40), _pose(x=41), _pose(x=42)],
        _thresholds(),
    )

    assert report.status == "needs_review"
    assert report.failed_rules == ()


def test_silhouette_jump_requires_keyframe() -> None:
    report = assess_sequence(
        [_pose(x=8), _pose(x=88)],
        _thresholds(),
    )

    assert report.status == "needs_keyframe"
    assert "adjacent_delta" in report.failed_rules
    assert "center_drift" in report.failed_rules


def test_alpha_growth_cannot_be_auto_approved() -> None:
    report = assess_sequence(
        [
            _pose(x=55, y=70, width=20, height=40),
            _pose(x=40, y=20, width=50, height=90),
        ],
        _thresholds(),
    )

    assert report.status == "needs_review"
    assert "alpha_growth" in report.failed_rules


def test_baseline_jump_requires_keyframe() -> None:
    report = assess_sequence(
        [_pose(y=20), _pose(y=45)],
        _thresholds(),
    )

    assert report.status == "needs_keyframe"
    assert "baseline_drift" in report.failed_rules


def test_empty_foreground_requires_keyframe() -> None:
    report = assess_sequence(
        [_pose(), Image.new("RGBA", (128, 128), (0, 0, 0, 0))],
        _thresholds(),
    )

    assert report.status == "needs_keyframe"
    assert "empty_foreground" in report.failed_rules
