from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence


ProviderName = Literal["film", "rife"]


class InterpolationError(RuntimeError):
    pass


@dataclass(frozen=True)
class InterpolationRouter:
    large_motion_threshold: float

    def __post_init__(self) -> None:
        if not 0 <= self.large_motion_threshold <= 1:
            raise ValueError("large motion threshold must be between zero and one")

    def select(self, normalized_motion: float) -> ProviderName:
        if not 0 <= normalized_motion <= 1:
            raise ValueError("normalized motion must be between zero and one")
        return (
            "film"
            if normalized_motion >= self.large_motion_threshold
            else "rife"
        )


@dataclass(frozen=True)
class FilmProvider:
    repo: Path
    model: Path
    timeout_seconds: int = 300
    name: ProviderName = "film"

    def preflight(self) -> None:
        cli = self.repo / "eval/interpolator_cli.py"
        if not self.repo.is_dir() or not cli.is_file():
            raise InterpolationError(f"FILM repository is unavailable: {self.repo}")
        if not (self.model / "saved_model.pb").is_file():
            raise InterpolationError(f"FILM SavedModel is unavailable: {self.model}")

    def command(self, pair_dir: Path, times: int) -> list[str]:
        if times <= 0:
            raise ValueError("FILM interpolation count must be positive")
        return [
            sys.executable,
            "-m",
            "eval.interpolator_cli",
            "--pattern",
            str(pair_dir),
            "--model_path",
            str(self.model),
            "--times_to_interpolate",
            str(times),
        ]

    def run(self, pair_dir: Path, times: int) -> subprocess.CompletedProcess[str]:
        self.preflight()
        return _run(self.command(pair_dir, times), self.repo, self.timeout_seconds)


@dataclass(frozen=True)
class RifeProvider:
    repo: Path
    model: Path | None = None
    timeout_seconds: int = 300
    name: ProviderName = "rife"

    def preflight(self) -> None:
        cli = self.repo / "inference_img.py"
        if not self.repo.is_dir() or not cli.is_file():
            raise InterpolationError(f"RIFE repository is unavailable: {self.repo}")
        model = self.model or self.repo / "train_log"
        if not model.is_dir() or not any(model.glob("*.pkl")):
            raise InterpolationError(f"RIFE weights are unavailable: {model}")

    def command(self, start: Path, end: Path, exponent: int) -> list[str]:
        if exponent <= 0:
            raise ValueError("RIFE exponent must be positive")
        return [
            sys.executable,
            str(self.repo / "inference_img.py"),
            "--img",
            str(start),
            str(end),
            "--exp",
            str(exponent),
        ]

    def run(
        self, start: Path, end: Path, exponent: int
    ) -> subprocess.CompletedProcess[str]:
        self.preflight()
        return _run(
            self.command(start, end, exponent),
            self.repo,
            self.timeout_seconds,
        )


def ordered_timestamps(exponent: int) -> tuple[float, ...]:
    if exponent <= 0:
        raise ValueError("interpolation exponent must be positive")
    denominator = 2**exponent
    return tuple(index / denominator for index in range(1, denominator))


def _run(
    command: Sequence[str], cwd: Path, timeout_seconds: int
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=True,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise InterpolationError(
            f"interpolation timed out after {timeout_seconds} seconds"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "provider failed").strip()
        raise InterpolationError(detail) from exc
