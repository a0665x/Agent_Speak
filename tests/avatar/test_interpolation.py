import sys
from pathlib import Path

import pytest

from AI_Avatar.tools.avatar_assets.interpolation import (
    FilmProvider,
    InterpolationError,
    InterpolationRouter,
    RifeProvider,
    ordered_timestamps,
)


def test_large_motion_routes_to_film() -> None:
    router = InterpolationRouter(large_motion_threshold=0.22)

    assert router.select(normalized_motion=0.41) == "film"


def test_small_motion_routes_to_rife() -> None:
    router = InterpolationRouter(large_motion_threshold=0.22)

    assert router.select(normalized_motion=0.08) == "rife"


def test_router_rejects_unbounded_motion_score() -> None:
    router = InterpolationRouter(large_motion_threshold=0.22)

    with pytest.raises(ValueError, match="between zero and one"):
        router.select(normalized_motion=1.4)


def test_film_builds_official_cli_shape(tmp_path: Path) -> None:
    provider = FilmProvider(
        repo=tmp_path / "film",
        model=tmp_path / "saved_model",
    )

    command = provider.command(tmp_path / "pair", times=2)

    assert command[:3] == [sys.executable, "-m", "eval.interpolator_cli"]
    assert command[command.index("--times_to_interpolate") + 1] == "2"
    assert command[command.index("--pattern") + 1] == str(tmp_path / "pair")


def test_rife_requests_four_way_interpolation(tmp_path: Path) -> None:
    provider = RifeProvider(repo=tmp_path / "rife")

    command = provider.command(
        tmp_path / "a.png",
        tmp_path / "b.png",
        exponent=2,
    )

    assert command[-2:] == ["--exp", "2"]
    assert command[1].endswith("inference_img.py")


def test_provider_preflight_requires_repo_and_weights(tmp_path: Path) -> None:
    provider = FilmProvider(
        repo=tmp_path / "film",
        model=tmp_path / "saved_model",
    )

    with pytest.raises(InterpolationError, match="FILM repository"):
        provider.preflight()


def test_ordered_timestamps_excludes_source_endpoints() -> None:
    assert ordered_timestamps(exponent=2) == (0.25, 0.5, 0.75)
