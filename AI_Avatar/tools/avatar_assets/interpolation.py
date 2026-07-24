from __future__ import annotations

import json
import subprocess
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, Sequence

import numpy as np
from PIL import Image


ProviderName = Literal["film", "rife"]


class InterpolationError(RuntimeError):
    pass


class PairProvider(Protocol):
    name: ProviderName

    def generate(
        self,
        start: Path,
        end: Path,
        work_dir: Path,
        exponent: int,
    ) -> tuple[Path, ...]: ...


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
        self,
        start: Path,
        end: Path,
        exponent: int,
        *,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.preflight()
        return _run(
            self.command(start, end, exponent),
            cwd or self.repo,
            self.timeout_seconds,
        )


def ordered_timestamps(exponent: int) -> tuple[float, ...]:
    if exponent <= 0:
        raise ValueError("interpolation exponent must be positive")
    denominator = 2**exponent
    return tuple(index / denominator for index in range(1, denominator))


def normalized_motion_score(start: Path, end: Path) -> float:
    with Image.open(start) as first_image, Image.open(end) as second_image:
        first = np.asarray(first_image.convert("RGBA"))[:, :, 3] > 0
        second = np.asarray(second_image.convert("RGBA"))[:, :, 3] > 0
    if first.shape != second.shape:
        raise ValueError("interpolation endpoints must have matching dimensions")
    union = np.logical_or(first, second)
    if not union.any():
        return 0.0
    changed = np.logical_xor(first, second)
    return float(changed.sum() / union.sum())


def copy_intermediate_frames(
    generated: Sequence[Path],
    destination: Path,
    *,
    prefix: str,
) -> tuple[Path, ...]:
    if len(generated) < 3:
        raise InterpolationError("provider did not produce intermediate frames")
    interior = generated[1:-1]
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for index, source in enumerate(interior, start=1):
        if not source.is_file():
            raise InterpolationError(f"generated frame is missing: {source}")
        target = destination / f"{prefix}_{index:03d}.png"
        shutil.copy2(source, target)
        copied.append(target)
    return tuple(copied)


@dataclass(frozen=True)
class FilmPairProvider:
    provider: FilmProvider
    name: ProviderName = "film"

    def generate(
        self,
        start: Path,
        end: Path,
        work_dir: Path,
        exponent: int,
    ) -> tuple[Path, ...]:
        pair = work_dir / "pair"
        pair.mkdir(parents=True, exist_ok=True)
        shutil.copy2(start, pair / "frame_000.png")
        shutil.copy2(end, pair / "frame_001.png")
        self.provider.run(pair, times=exponent)
        generated = tuple(sorted((pair / "interpolated_frames").glob("*.png")))
        if len(generated) < 3:
            raise InterpolationError("FILM did not produce an interpolated sequence")
        return generated


@dataclass(frozen=True)
class RifePairProvider:
    provider: RifeProvider
    name: ProviderName = "rife"

    def generate(
        self,
        start: Path,
        end: Path,
        work_dir: Path,
        exponent: int,
    ) -> tuple[Path, ...]:
        work_dir.mkdir(parents=True, exist_ok=True)
        first = work_dir / "frame_000.png"
        second = work_dir / "frame_001.png"
        shutil.copy2(start, first)
        shutil.copy2(end, second)
        model = self.provider.model or self.provider.repo / "train_log"
        link = work_dir / "train_log"
        if not link.exists():
            link.symlink_to(model.resolve(), target_is_directory=True)
        self.provider.run(first, second, exponent, cwd=work_dir)
        generated = tuple(sorted((work_dir / "output").glob("*.png")))
        if len(generated) < 3:
            raise InterpolationError("RIFE did not produce an interpolated sequence")
        return generated


@dataclass(frozen=True)
class RoutedInterpolator:
    router: InterpolationRouter
    film: PairProvider
    rife: PairProvider
    candidate_root: Path
    exponent: int = 2
    preferred: Literal["auto", "film", "rife"] = "auto"

    def __call__(self, start: Path, end: Path, label: str) -> tuple[Path, ...]:
        if not label or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_"
            for character in label
        ):
            raise ValueError("interpolation label must be lowercase snake_case")
        selected: ProviderName
        if self.preferred == "auto":
            selected = self.router.select(normalized_motion_score(start, end))
        else:
            selected = self.preferred
        provider = self.film if selected == "film" else self.rife
        generated = provider.generate(
            start,
            end,
            self.candidate_root / "work" / label,
            self.exponent,
        )
        return copy_intermediate_frames(
            generated,
            self.candidate_root / "transitions" / label,
            prefix=label,
        )


def build_routed_interpolator(
    config_path: Path,
    *,
    project_root: Path,
    candidate_root: Path,
    preferred: Literal["auto", "film", "rife"] = "auto",
) -> RoutedInterpolator:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != "1.0":
        raise InterpolationError("interpolation provider config version is invalid")
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        raise InterpolationError("interpolation provider config is missing providers")
    film = providers.get("film")
    rife = providers.get("rife")
    if not isinstance(film, dict) or not isinstance(rife, dict):
        raise InterpolationError("FILM and RIFE provider configs are required")

    def path_from(config: dict[str, object], key: str) -> Path:
        value = config.get(key)
        if not isinstance(value, str) or not value:
            raise InterpolationError(f"provider {key} must be a project-relative path")
        path = (project_root / value).resolve()
        if not path.is_relative_to(project_root.resolve()):
            raise InterpolationError(f"provider {key} must stay below project root")
        return path

    threshold = payload.get("large_motion_threshold")
    exponent = payload.get("candidate_exponent")
    timeout = payload.get("timeout_seconds")
    if not isinstance(threshold, (int, float)):
        raise InterpolationError("large_motion_threshold must be numeric")
    if not isinstance(exponent, int) or exponent <= 0:
        raise InterpolationError("candidate_exponent must be positive")
    if not isinstance(timeout, int) or timeout <= 0:
        raise InterpolationError("timeout_seconds must be positive")
    return RoutedInterpolator(
        router=InterpolationRouter(float(threshold)),
        film=FilmPairProvider(
            FilmProvider(
                repo=path_from(film, "repo_path"),
                model=path_from(film, "model_path"),
                timeout_seconds=timeout,
            )
        ),
        rife=RifePairProvider(
            RifeProvider(
                repo=path_from(rife, "repo_path"),
                model=path_from(rife, "model_path"),
                timeout_seconds=timeout,
            )
        ),
        candidate_root=candidate_root,
        exponent=exponent,
        preferred=preferred,
    )


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
