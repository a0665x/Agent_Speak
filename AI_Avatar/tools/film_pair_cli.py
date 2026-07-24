#!/usr/bin/env python3
"""Run one FILM frame pair locally without the Apache Beam evaluation CLI."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--pair", type=Path, required=True)
    parser.add_argument("--model_path", type=Path, required=True)
    parser.add_argument("--times_to_interpolate", type=int, required=True)
    return parser


def _load_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as source:
        return np.asarray(source.convert("RGBA"), dtype=np.float32) / 255.0


def _save_rgba(path: Path, image: np.ndarray) -> None:
    encoded = np.rint(np.clip(image, 0.0, 1.0) * 255.0).astype(np.uint8)
    Image.fromarray(encoded, mode="RGBA").save(path)


def _morph_alpha(
    first_alpha: np.ndarray,
    second_alpha: np.ndarray,
    time: float,
) -> np.ndarray:
    first_mask = first_alpha[..., 0] > 0.5
    second_mask = second_alpha[..., 0] > 0.5
    first_sdf = distance_transform_edt(first_mask) - distance_transform_edt(
        ~first_mask
    )
    second_sdf = distance_transform_edt(second_mask) - distance_transform_edt(
        ~second_mask
    )
    signed_distance = first_sdf * (1.0 - time) + second_sdf * time
    return np.clip(0.5 + signed_distance, 0.0, 1.0)[..., np.newaxis]


def _interpolate_rgba(model, start: np.ndarray, end: np.ndarray, time: float):
    first_alpha = start[..., 3:4]
    second_alpha = end[..., 3:4]
    batch_time = np.asarray([time], dtype=np.float32)
    rgb = model(
        (start[..., :3] * first_alpha)[np.newaxis, ...],
        (end[..., :3] * second_alpha)[np.newaxis, ...],
        batch_time,
    )[0]
    alpha = _morph_alpha(first_alpha, second_alpha, time)
    straight_rgb = np.divide(
        np.clip(rgb, 0.0, 1.0),
        np.maximum(alpha, 1.0 / 255.0),
        out=np.zeros_like(rgb),
        where=alpha > 1.0 / 255.0,
    )
    return np.concatenate((np.clip(straight_rgb, 0.0, 1.0), alpha), axis=2)


def main() -> int:
    args = _parser().parse_args()
    if args.times_to_interpolate <= 0:
        raise ValueError("times_to_interpolate must be positive")
    sources = sorted(args.pair.glob("*.png"))
    if len(sources) != 2:
        raise ValueError(f"expected exactly two PNG inputs below {args.pair}")
    sys.path.insert(0, str(args.repo))
    from eval.interpolator import Interpolator

    model = Interpolator(str(args.model_path), align=64)
    start = _load_rgba(sources[0])
    end = _load_rgba(sources[1])
    if start.shape != end.shape:
        raise ValueError("FILM pair dimensions must match")
    output = args.pair / "interpolated_frames"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    count = 2**args.times_to_interpolate
    _save_rgba(output / "frame_000.png", start)
    for index in range(1, count):
        frame = _interpolate_rgba(model, start, end, index / count)
        _save_rgba(output / f"frame_{index:03d}.png", frame)
    _save_rgba(output / f"frame_{count:03d}.png", end)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
