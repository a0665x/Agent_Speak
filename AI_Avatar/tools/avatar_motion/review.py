from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class ReviewThresholds:
    max_adjacent_delta: float
    max_center_drift: float
    max_baseline_drift: float
    max_detached_area_ratio: float

    def __post_init__(self) -> None:
        for name, value in (
            ("max_adjacent_delta", self.max_adjacent_delta),
            ("max_center_drift", self.max_center_drift),
            ("max_baseline_drift", self.max_baseline_drift),
            ("max_detached_area_ratio", self.max_detached_area_ratio),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True)
class CandidateReview:
    status: str
    failed_rules: tuple[str, ...]
    metrics: dict[str, float]


def _mask(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGBA"))[:, :, 3] > 8


def _geometry(mask: np.ndarray) -> tuple[float, float]:
    coordinates = np.argwhere(mask)
    if not coordinates.size:
        return 0.0, 0.0
    _top, left = coordinates.min(axis=0)
    bottom, right = coordinates.max(axis=0)
    return float((left + right + 1) / 2), float(bottom + 1)


def _detached_ratio(mask: np.ndarray) -> float:
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8),
        connectivity=8,
    )
    if count <= 2:
        return 0.0
    areas = sorted((int(stats[index, cv2.CC_STAT_AREA]) for index in range(1, count)), reverse=True)
    return sum(areas[1:]) / max(1, sum(areas))


def review_candidate(
    candidate: Image.Image,
    previous: Image.Image,
    thresholds: ReviewThresholds,
) -> CandidateReview:
    if candidate.size != previous.size:
        return CandidateReview(
            status="needs_keyframe",
            failed_rules=("canvas",),
            metrics={},
        )
    candidate_mask = _mask(candidate)
    previous_mask = _mask(previous)
    if not candidate_mask.any():
        return CandidateReview(
            status="needs_keyframe",
            failed_rules=("empty_foreground",),
            metrics={},
        )
    union = np.logical_or(candidate_mask, previous_mask)
    changed = np.logical_xor(candidate_mask, previous_mask)
    adjacent_delta = float(changed.sum() / max(1, int(union.sum())))
    candidate_center, candidate_baseline = _geometry(candidate_mask)
    previous_center, previous_baseline = _geometry(previous_mask)
    width, height = candidate.size
    center_drift = abs(candidate_center - previous_center) / width
    baseline_drift = abs(candidate_baseline - previous_baseline) / height
    detached_ratio = _detached_ratio(candidate_mask)
    metrics = {
        "adjacent_delta": adjacent_delta,
        "center_drift": center_drift,
        "baseline_drift": baseline_drift,
        "detached_area_ratio": detached_ratio,
    }
    failed: list[str] = []
    if adjacent_delta > thresholds.max_adjacent_delta:
        failed.append("adjacent_delta")
    if center_drift > thresholds.max_center_drift:
        failed.append("center_drift")
    if baseline_drift > thresholds.max_baseline_drift:
        failed.append("baseline_drift")
    if detached_ratio > thresholds.max_detached_area_ratio:
        failed.append("detached_component")
    return CandidateReview(
        status="needs_keyframe" if failed else "needs_review",
        failed_rules=tuple(failed),
        metrics=metrics,
    )

