import httpx
import pytest

from agent_speak.asr_worker import create_asr_worker
from agent_speak.config import Settings
from tests.audio_fixtures import wav_bytes


class FakeASR:
    device = "cuda"

    def __init__(self) -> None:
        self.warmed = False
        self.languages: list[str | None] = []

    def warm(self) -> None:
        self.warmed = True

    def transcribe(self, audio: bytes, language: str | None = "configured") -> str:
        assert self.warmed
        self.languages.append(language)
        return "即時測試"


@pytest.mark.anyio
async def test_internal_worker_warms_and_transcribes_bounded_wav(tmp_path) -> None:
    provider = FakeASR()
    app = create_asr_worker(
        provider=provider,
        settings=Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://worker"
        ) as client:
            health = await client.get("/internal/v1/health")
            result = await client.post(
                "/internal/v1/asr?mode=final",
                content=wav_bytes(),
                headers={"content-type": "audio/wav"},
            )
    assert provider.warmed is True
    assert health.json()["device"] == "cuda"
    assert result.json() == {"text": "即時測試", "device": "cuda", "mode": "final"}


@pytest.mark.anyio
async def test_internal_worker_rejects_wrong_media_type_and_oversized_audio(tmp_path) -> None:
    app = create_asr_worker(
        provider=FakeASR(),
        settings=Settings(
            data_dir=tmp_path / "data",
            runtime_dir=tmp_path / "runtime",
            max_audio_bytes=100,
        ),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://worker"
        ) as client:
            wrong = await client.post(
                "/internal/v1/asr", content=b"x", headers={"content-type": "application/octet-stream"}
            )
            large = await client.post(
                "/internal/v1/asr", content=wav_bytes(), headers={"content-type": "audio/wav"}
            )
    assert wrong.status_code == 415
    assert large.status_code == 413


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("speech_language", "expected_hint"),
    [("zh-TW", "zh"), ("en", "en"), ("ja", "ja"), ("ko", "ko"), ("auto", None)],
)
async def test_internal_worker_maps_public_language_to_whisper_hint(
    tmp_path, speech_language: str, expected_hint: str | None
) -> None:
    provider = FakeASR()
    app = create_asr_worker(
        provider=provider,
        settings=Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://worker"
        ) as client:
            response = await client.post(
                "/internal/v1/asr",
                params={"mode": "partial", "speech_language": speech_language},
                content=wav_bytes(),
                headers={"content-type": "audio/wav"},
            )

    assert response.status_code == 200
    assert provider.languages == [expected_hint]


@pytest.mark.anyio
async def test_internal_worker_rejects_unknown_public_language_before_inference(tmp_path) -> None:
    provider = FakeASR()
    app = create_asr_worker(
        provider=provider,
        settings=Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://worker"
        ) as client:
            response = await client.post(
                "/internal/v1/asr",
                params={"speech_language": "fr"},
                content=wav_bytes(),
                headers={"content-type": "audio/wav"},
            )

    assert response.status_code == 422
    assert provider.languages == []
