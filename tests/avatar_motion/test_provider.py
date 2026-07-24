from __future__ import annotations

import base64
from pathlib import Path

import httpx
from PIL import Image

from AI_Avatar.tools.avatar_motion.prompt import build_prompt_packet
from AI_Avatar.tools.avatar_motion.provider import GptImageProvider


def _png(path: Path, color: tuple[int, int, int]) -> Path:
    Image.new("RGB", (16, 16), color).save(path)
    return path


def test_provider_never_serializes_api_key(monkeypatch, tmp_path: Path) -> None:
    encoded = base64.b64encode((_png(tmp_path / "result.png", (1, 2, 3))).read_bytes())
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"x-request-id": "request-1"},
            json={"data": [{"b64_json": encoded.decode("ascii")}]},
        )

    packet = build_prompt_packet(
        canonical_reference=_png(tmp_path / "reference.png", (10, 10, 10)),
        current_pose_map=_png(tmp_path / "pose.png", (20, 20, 20)),
        nearest_approved_frame=_png(tmp_path / "neighbor.png", (30, 30, 30)),
        identity_invariants=("same character",),
        geometry_invariants=("locked feet",),
        canvas=(512, 512),
        background="#00ff66",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = GptImageProvider(client=client).edit(
        packet,
        tmp_path / "opaque.png",
    )

    assert result.output_path.is_file()
    assert "secret-value" not in repr(result.safe_metadata)
    assert requests[0].headers["authorization"] == "Bearer secret-value"
    assert result.safe_metadata["request_id"] == "request-1"


def test_provider_requires_environment_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = GptImageProvider(
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: None))
    )

    try:
        provider.edit(
            build_prompt_packet(
                canonical_reference=Path("reference.png"),
                current_pose_map=Path("pose.png"),
                nearest_approved_frame=Path("neighbor.png"),
                identity_invariants=(),
                geometry_invariants=(),
                canvas=(512, 512),
                background="#00ff66",
            ),
            tmp_path / "opaque.png",
        )
    except ValueError as error:
        assert "OPENAI_API_KEY" in str(error)
    else:
        raise AssertionError("provider accepted missing API key")
