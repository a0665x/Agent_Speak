from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

import numpy as np
from PIL import Image


QualityStatus = Literal["approved", "needs_review", "needs_keyframe"]


@dataclass(frozen=True)
class QualityThresholds:
    max_adjacent_delta: float
    max_alpha_growth: float
    max_center_drift: float
    max_baseline_drift: float

    def __post_init__(self) -> None:
        for name, value in (
            ("max_adjacent_delta", self.max_adjacent_delta),
            ("max_alpha_growth", self.max_alpha_growth),
            ("max_center_drift", self.max_center_drift),
            ("max_baseline_drift", self.max_baseline_drift),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True)
class QualityReport:
    status: QualityStatus
    metrics: Mapping[str, float]
    failed_rules: tuple[str, ...]


@dataclass(frozen=True)
class _FrameMetrics:
    mask: np.ndarray
    area: int
    center_x: float
    baseline: float
    digest: str


def _frame_metrics(image: Image.Image) -> _FrameMetrics | None:
    rgba = np.asarray(image.convert("RGBA"))
    mask = rgba[:, :, 3] > 0
    coordinates = np.argwhere(mask)
    if not coordinates.size:
        return None
    top, left = coordinates.min(axis=0)
    bottom, right = coordinates.max(axis=0)
    del top
    return _FrameMetrics(
        mask=mask,
        area=int(mask.sum()),
        center_x=float((left + right + 1) / 2),
        baseline=float(bottom + 1),
        digest=hashlib.sha256(rgba.tobytes()).hexdigest(),
    )


def assess_sequence(
    frames: Sequence[Image.Image],
    thresholds: QualityThresholds,
) -> QualityReport:
    if len(frames) < 2:
        raise ValueError("quality assessment requires at least two frames")
    size = frames[0].size
    if any(frame.size != size for frame in frames):
        raise ValueError("all frames must have the same dimensions")
    metrics = [_frame_metrics(frame) for frame in frames]
    if any(metric is None for metric in metrics):
        return QualityReport(
            status="needs_keyframe",
            metrics=MappingProxyType({"empty_foreground_count": 1.0}),
            failed_rules=("empty_foreground",),
        )
    concrete = [metric for metric in metrics if metric is not None]
    width, height = size
    adjacent_deltas: list[float] = []
    alpha_growth: list[float] = []
    center_drifts: list[float] = []
    baseline_drifts: list[float] = []
    for first, second in zip(concrete, concrete[1:]):
        union = np.logical_or(first.mask, second.mask)
        changed = np.logical_xor(first.mask, second.mask)
        adjacent_deltas.append(
            float(changed.sum() / max(1, int(union.sum())))
        )
        alpha_growth.append(
            abs(second.area - first.area) / max(1, first.area)
        )
        center_drifts.append(abs(second.center_x - first.center_x) / width)
        baseline_drifts.append(abs(second.baseline - first.baseline) / height)

    values = {
        "max_adjacent_delta": max(adjacent_deltas, default=0.0),
        "max_alpha_growth": max(alpha_growth, default=0.0),
        "max_center_drift": max(center_drifts, default=0.0),
        "max_baseline_drift": max(baseline_drifts, default=0.0),
        "duplicate_ratio": 1
        - len({metric.digest for metric in concrete}) / len(concrete),
    }
    failed: list[str] = []
    if values["max_adjacent_delta"] > thresholds.max_adjacent_delta:
        failed.append("adjacent_delta")
    if values["max_alpha_growth"] > thresholds.max_alpha_growth:
        failed.append("alpha_growth")
    if values["max_center_drift"] > thresholds.max_center_drift:
        failed.append("center_drift")
    if values["max_baseline_drift"] > thresholds.max_baseline_drift:
        failed.append("baseline_drift")

    fatal = {"center_drift", "baseline_drift"}
    if "adjacent_delta" in failed and "alpha_growth" not in failed:
        fatal.add("adjacent_delta")
    status: QualityStatus = (
        "needs_keyframe" if fatal.intersection(failed) else "needs_review"
    )
    return QualityReport(
        status=status,
        metrics=MappingProxyType(values),
        failed_rules=tuple(failed),
    )
