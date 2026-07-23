from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings
from agent_speak.errors import PlatformError
from tests.audio_fixtures import wav_bytes


class FakeCloneClient:
    def __init__(self, *, ready: bool = True, error: PlatformError | None = None) -> None:
        self.ready = ready
        self.error = error
        self.calls: list[tuple[str, bytes | None]] = []

    def is_ready(self) -> bool:
        return self.ready

    def synthesize(self, *, text: str, reference_wav: bytes | None) -> bytes:
        self.calls.append((text, reference_wav))
        if self.error is not None:
            raise self.error
        return wav_bytes(rate=48_000, seconds=1.0)


def clone_app(tmp_path: Path, *, client: FakeCloneClient | None = None):
    return create_app(
        Settings(
            data_dir=tmp_path / "data",
            runtime_dir=tmp_path / "runtime",
            gpu_mode="tts",
            effective_accelerator="nvidia",
        ),
        tts_clone=client or FakeCloneClient(),
    )


@pytest.mark.anyio
async def test_clone_status_reports_wrong_mode_without_contacting_worker(tmp_path: Path) -> None:
    fake = FakeCloneClient()
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            runtime_dir=tmp_path / "runtime",
            gpu_mode="asr",
        ),
        tts_clone=fake,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/tts-clone/status")

    assert response.json()["state"] == "stopped"
    assert response.json()["error_code"] == "wrong_gpu_mode"
    assert response.json()["operator_hint"] == "./run.sh --tts-up"


@pytest.mark.anyio
async def test_reference_validation_never_writes_audio(tmp_path: Path) -> None:
    app = clone_app(tmp_path)
    before = set(tmp_path.rglob("*"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tts-clone/reference/validate",
            content=wav_bytes(seconds=10.0),
            headers={"content-type": "audio/wav"},
        )

    assert response.status_code == 200
    assert response.json()["quality"] == "good"
    created = set(tmp_path.rglob("*")) - before
    assert not any(path.suffix == ".wav" for path in created)


@pytest.mark.anyio
async def test_synthesis_returns_wav_without_artifact(tmp_path: Path) -> None:
    fake = FakeCloneClient()
    app = clone_app(tmp_path, client=fake)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tts-clone/synthesize",
            data={"text": "Hello", "style_cues": "warm", "use_clone": "true"},
            files={
                "reference": (
                    "reference.wav",
                    wav_bytes(seconds=10.0),
                    "audio/wav",
                )
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-agent-speak-model"] == "voxcpm2"
    assert fake.calls[0][0] == "(warm delivery)Hello"
    assert fake.calls[0][1] is not None
    assert not list((tmp_path / "data").rglob("*.wav"))
    assert not list((tmp_path / "runtime").rglob("*.wav"))


@pytest.mark.anyio
async def test_clone_synthesis_requires_valid_reference_when_enabled(tmp_path: Path) -> None:
    app = clone_app(tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        missing = await client.post(
            "/api/v1/tts-clone/synthesize",
            data={"text": "Hello", "use_clone": "true"},
        )
        bad_cue = await client.post(
            "/api/v1/tts-clone/synthesize",
            data={"text": "Hello", "style_cues": "[laugh]", "use_clone": "false"},
        )

    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "reference_required"
    assert bad_cue.status_code == 400
    assert bad_cue.json()["error"]["code"] == "invalid_style_cue"


@pytest.mark.anyio
async def test_clone_endpoints_reject_invalid_media_and_wrong_mode(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            runtime_dir=tmp_path / "runtime",
            gpu_mode="asr",
        ),
        tts_clone=FakeCloneClient(),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        invalid_media = await client.post(
            "/api/v1/tts-clone/reference/validate",
            content=b"not audio",
            headers={"content-type": "application/octet-stream"},
        )
        wrong_mode = await client.post(
            "/api/v1/tts-clone/synthesize",
            data={"text": "Hello", "use_clone": "false"},
        )

    assert invalid_media.status_code == 415
    assert invalid_media.json()["error"]["code"] == "unsupported_media_type"
    assert wrong_mode.status_code == 409
    assert wrong_mode.json()["error"]["code"] == "wrong_gpu_mode"


@pytest.mark.anyio
async def test_clone_openapi_is_localized_in_all_four_languages(tmp_path: Path) -> None:
    app = clone_app(tmp_path)
    expected = {
        "en": "Check TTS clone readiness",
        "zh-TW": "檢查 TTS 克隆就緒狀態",
        "ja": "TTS クローンの準備状態を確認",
        "ko": "TTS 클론 준비 상태 확인",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for locale, summary in expected.items():
            schema = (await client.get(f"/openapi.json?lang={locale}")).json()
            operation = schema["paths"]["/api/v1/tts-clone/status"]["get"]
            assert operation["summary"] == summary
            assert operation["tags"]
            assert "TTSCloneStatus" in schema["components"]["schemas"]
