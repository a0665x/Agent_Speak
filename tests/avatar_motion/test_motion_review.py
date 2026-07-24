from __future__ import annotations

from PIL import Image, ImageDraw

from AI_Avatar.tools.avatar_motion.review import (
    ReviewThresholds,
    review_candidate,
)


def _pose(x: int = 30, *, detached: bool = False) -> Image.Image:
    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x, 18, x + 30, 84), radius=8, fill=(100, 80, 60, 255))
    if detached:
        draw.rectangle((2, 2, 4, 4), fill=(100, 80, 60, 255))
    return image


def _thresholds() -> ReviewThresholds:
    return ReviewThresholds(
        max_adjacent_delta=0.25,
        max_center_drift=0.12,
        max_baseline_drift=0.05,
        max_detached_area_ratio=0.001,
    )


def test_clean_candidate_still_requires_human_review() -> None:
    report = review_candidate(_pose(31), _pose(30), _thresholds())

    assert report.status == "needs_review"
    assert report.failed_rules == ()


def test_review_rejects_detached_component_and_boundary_jump() -> None:
    report = review_candidate(_pose(60, detached=True), _pose(10), _thresholds())

    assert report.status == "needs_keyframe"
    assert "detached_component" in report.failed_rules
    assert "adjacent_delta" in report.failed_rules


def test_review_rejects_wrong_canvas() -> None:
    report = review_candidate(
        Image.new("RGBA", (64, 64), (0, 0, 0, 0)),
        _pose(),
        _thresholds(),
    )

    assert report.status == "needs_keyframe"
    assert "canvas" in report.failed_rules

