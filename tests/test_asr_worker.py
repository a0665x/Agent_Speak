import asyncio
import json

import httpx
import pytest

from agent_speak.asr_model_manager import ASRModelManager
from agent_speak.asr_worker import create_asr_worker
from agent_speak.config import Settings
from agent_speak.errors import PlatformError
from agent_speak.model_ids import ASRModelId
from tests.audio_fixtures import wav_bytes


class FakeASR:
    device = "cuda"

    def __init__(self, name: str = "fake") -> None:
        self.name = name
        self.warmed = False
        self.closed = False
        self.languages: list[str | None] = []

    def warm(self) -> None:
        self.warmed = True

    def close(self) -> None:
        self.closed = True

    def transcribe(self, audio: bytes, language: str | None = "configured") -> str:
        assert self.warmed
        self.languages.append(language)
        return "即時測試"


class FailingASR(FakeASR):
    def transcribe(self, audio: bytes, language: str | None = "configured") -> str:
        raise PlatformError(
            "asr_failed",
            "ASR could not transcribe the audio",
            status_code=500,
            stage="asr",
            retryable=True,
        ) from RuntimeError("private provider details")


def fake_manager() -> tuple[ASRModelManager, dict[ASRModelId, list[FakeASR]]]:
    instances: dict[ASRModelId, list[FakeASR]] = {
        "faster-whisper-small": [],
        "breeze-asr-25": [],
        "qwen3-asr-1.7b": [],
    }

    def factory(model_id: ASRModelId):
        def create() -> FakeASR:
            provider = FakeASR(model_id)
            instances[model_id].append(provider)
            return provider

        return create

    return (
        ASRModelManager(
            factories={model_id: factory(model_id) for model_id in instances},
            device="cuda",
            memory_cleanup=lambda: None,
        ),
        instances,
    )


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
    assert result.json() == {
        "text": "即時測試",
        "device": "cuda",
        "mode": "final",
        "asr_model": "faster-whisper-small",
    }


@pytest.mark.anyio
async def test_internal_worker_logs_provider_failure_without_audio_or_error_message(tmp_path) -> None:
    app = create_asr_worker(
        provider=FailingASR(),
        settings=Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://worker"
        ) as client:
            await client.post(
                "/internal/v1/models/lease/private-session",
                params={"asr_model": "faster-whisper-small"},
            )
            response = await client.post(
                "/internal/v1/asr",
                params={"mode": "partial", "session_id": "private-session"},
                content=wav_bytes(),
                headers={"content-type": "audio/wav"},
            )

    records = [
        json.loads(line)
        for line in (tmp_path / "runtime" / "logs" / "asr-worker.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    failure = next(record for record in records if record["event"] == "asr.inference.failed")
    rendered = json.dumps(failure)
    assert response.status_code == 500
    assert failure["model"] == "faster-whisper-small"
    assert failure["mode"] == "partial"
    assert failure["error_code"] == "asr_failed"
    assert failure["exception_type"] == "RuntimeError"
    assert "private-session" not in rendered
    assert "private provider details" not in rendered


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


@pytest.mark.anyio
async def test_internal_worker_exposes_manager_state_and_switches_model(tmp_path) -> None:
    manager, instances = fake_manager()
    app = create_asr_worker(
        manager=manager,
        settings=Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
    )

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://worker") as client:
            initial = await client.get("/internal/v1/models")
            switching = await client.put(
                "/internal/v1/models/active",
                json={"asr_model": "breeze-asr-25"},
            )
            for _ in range(20):
                await asyncio.sleep(0)
                ready = await client.get("/internal/v1/models")
                if ready.json()["state"] == "ready" and ready.json()["active_asr_model"] == "breeze-asr-25":
                    break

    assert initial.json()["active_asr_model"] == "qwen3-asr-1.7b"
    assert switching.status_code in {200, 202}
    assert ready.json()["active_asr_model"] == "breeze-asr-25"
    assert instances["qwen3-asr-1.7b"][0].closed is True
    assert instances["breeze-asr-25"][0].warmed is True


@pytest.mark.anyio
async def test_internal_worker_lease_blocks_conflicting_activation(tmp_path) -> None:
    manager, _ = fake_manager()
    app = create_asr_worker(
        manager=manager,
        settings=Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
    )

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://worker") as client:
            leased = await client.post(
                "/internal/v1/models/lease/session-a",
                params={"asr_model": "qwen3-asr-1.7b"},
            )
            conflict = await client.put(
                "/internal/v1/models/active",
                json={"asr_model": "breeze-asr-25"},
            )
            released_wrong = await client.delete("/internal/v1/models/lease/session-b")
            released = await client.delete("/internal/v1/models/lease/session-a")

    assert leased.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "model_in_use"
    assert released_wrong.json()["leased_by"] == "session-a"
    assert released.json()["leased_by"] is None


@pytest.mark.anyio
async def test_internal_worker_routes_transcription_through_frozen_model_lease(tmp_path) -> None:
    manager, instances = fake_manager()
    app = create_asr_worker(
        manager=manager,
        settings=Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
    )

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://worker") as client:
            await client.post(
                "/internal/v1/models/lease/session-a",
                params={"asr_model": "qwen3-asr-1.7b"},
            )
            response = await client.post(
                "/internal/v1/asr",
                params={
                    "mode": "partial",
                    "speech_language": "en",
                    "asr_model": "qwen3-asr-1.7b",
                    "session_id": "session-a",
                },
                content=wav_bytes(),
                headers={"content-type": "audio/wav"},
            )
            wrong_model = await client.post(
                "/internal/v1/asr",
                params={"asr_model": "breeze-asr-25", "session_id": "session-a"},
                content=wav_bytes(),
                headers={"content-type": "audio/wav"},
            )

    assert response.status_code == 200
    assert response.json()["asr_model"] == "qwen3-asr-1.7b"
    assert instances["qwen3-asr-1.7b"][0].languages == ["en"]
    assert wrong_model.status_code == 409
    assert wrong_model.json()["error"]["code"] == "model_not_ready"


@pytest.mark.anyio
async def test_internal_worker_rejects_unknown_model_id(tmp_path) -> None:
    manager, _ = fake_manager()
    app = create_asr_worker(
        manager=manager,
        settings=Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
    )

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://worker") as client:
            response = await client.put(
                "/internal/v1/models/active",
                json={"asr_model": "not-a-model"},
            )

    assert response.status_code == 422
