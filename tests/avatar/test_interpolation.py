import sys
from pathlib import Path

import pytest
from PIL import Image

from AI_Avatar.tools.avatar_assets.interpolation import (
    copy_intermediate_frames,
    build_routed_interpolator,
    FilmProvider,
    InterpolationError,
    InterpolationRouter,
    normalized_motion_score,
    RifeProvider,
    RoutedInterpolator,
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


def test_normalized_motion_score_distinguishes_static_and_large_motion(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.png"
    same = tmp_path / "same.png"
    moved = tmp_path / "moved.png"
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(8, 24):
        for y in range(16, 48):
            image.putpixel((x, y), (30, 40, 50, 255))
    image.save(first)
    image.save(same)
    shifted = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(40, 56):
        for y in range(16, 48):
            shifted.putpixel((x, y), (30, 40, 50, 255))
    shifted.save(moved)

    assert normalized_motion_score(first, same) == 0
    assert normalized_motion_score(first, moved) == 1


def test_copy_intermediate_frames_removes_source_endpoints(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    sources = []
    for index in range(5):
        path = generated / f"img{index}.png"
        Image.new("RGBA", (8, 8), (index, 0, 0, 255)).save(path)
        sources.append(path)

    copied = copy_intermediate_frames(
        sources,
        tmp_path / "candidate",
        prefix="idle_entry",
    )

    assert [path.name for path in copied] == [
        "idle_entry_001.png",
        "idle_entry_002.png",
        "idle_entry_003.png",
    ]
    assert Image.open(copied[0]).getpixel((0, 0))[0] == 1


def test_routed_interpolator_uses_film_for_large_motion(tmp_path: Path) -> None:
    start = tmp_path / "start.png"
    end = tmp_path / "end.png"
    Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(start)
    moved = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for x in range(20, 30):
        for y in range(8, 24):
            moved.putpixel((x, y), (30, 40, 50, 255))
    moved.save(end)
    calls: list[str] = []

    class FakeProvider:
        def __init__(self, name: str) -> None:
            self.name = name

        def generate(
            self,
            first: Path,
            second: Path,
            work_dir: Path,
            exponent: int,
        ) -> tuple[Path, ...]:
            calls.append(self.name)
            work_dir.mkdir(parents=True, exist_ok=True)
            output = []
            for index, source in enumerate((first, first, first, second, second)):
                path = work_dir / f"img{index}.png"
                path.write_bytes(source.read_bytes())
                output.append(path)
            return tuple(output)

    routed = RoutedInterpolator(
        router=InterpolationRouter(large_motion_threshold=0.22),
        film=FakeProvider("film"),
        rife=FakeProvider("rife"),
        candidate_root=tmp_path / "candidates",
        exponent=2,
    )

    frames = routed(start, end, "listening_entry")

    assert calls == ["film"]
    assert [frame.name for frame in frames] == [
        "listening_entry_001.png",
        "listening_entry_002.png",
        "listening_entry_003.png",
    ]


def test_build_routed_interpolator_uses_pinned_project_paths(tmp_path: Path) -> None:
    config = tmp_path / "providers.json"
    config.write_text(
        """
        {
          "version": "1.0",
          "large_motion_threshold": 0.22,
          "candidate_exponent": 2,
          "timeout_seconds": 180,
          "providers": {
            "film": {
              "repo_path": "AI_Avatar/.providers/film",
              "model_path": "models/avatar_interpolation/film/saved_model"
            },
            "rife": {
              "repo_path": "AI_Avatar/.providers/rife",
              "model_path": "models/avatar_interpolation/rife/train_log"
            }
          }
        }
        """,
        encoding="utf-8",
    )

    routed = build_routed_interpolator(
        config,
        project_root=tmp_path,
        candidate_root=tmp_path / "candidates",
        preferred="film",
    )

    assert routed.preferred == "film"
    assert routed.exponent == 2
    assert routed.film.provider.repo == tmp_path / "AI_Avatar/.providers/film"
    assert (
        routed.rife.provider.model
        == tmp_path / "models/avatar_interpolation/rife/train_log"
    )
