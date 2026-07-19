from pathlib import Path
import asyncio
import io
import stat
import time
import wave

import httpx
import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings
from agent_speak.pipeline import ProviderSet
from agent_speak.development import DevelopmentAgent, DevelopmentCorrection, DevelopmentEndpoint, DevelopmentTTS, DevelopmentVAD
from .audio_fixtures import wav_bytes


class FailedASR:
    def transcribe(self, audio: bytes) -> str:
        raise RuntimeError("development decoder failed")


class SlowASR:
    def __init__(self, heartbeat: asyncio.Event) -> None:
        self.heartbeat = heartbeat
        self.heartbeat_seen_during_call = False

    def transcribe(self, audio: bytes) -> str:
        time.sleep(0.15)
        self.heartbeat_seen_during_call = self.heartbeat.is_set()
        return "event loop remained responsive"


class BytesTTS:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def synthesize(self, text: str) -> bytes:
        return self.payload


def unsupported_wav_bytes() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(1)
        wav.setframerate(16_000)
        wav.writeframes(b"\x80" * 160)
    return output.getvalue()


async def post_oversized_first_chunk(app: object, path: str, limit: int) -> tuple[int, int]:
    receive_calls = 0
    messages: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls > 1:
            raise AssertionError("application drained the request after the byte limit was crossed")
        return {"type": "http.request", "body": b"x" * (limit + 1), "more_body": True}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"test"), (b"content-type", b"audio/wav")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    await app(scope, receive, send)  # type: ignore[misc]
    response_start = next(message for message in messages if message["type"] == "http.response.start")
    return int(response_start["status"]), receive_calls


@pytest.mark.anyio
async def test_separate_development_stage_apis_and_artifact(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime")
    app = create_app(settings, providers=ProviderSet.development())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        asr = await client.post("/api/v1/audio/asr", content=wav_bytes(), headers={"content-type": "audio/wav"})
        corrected = await client.post("/api/v1/text/correct", json={"text": "  hello   agent "})
        endpoint = await client.post("/api/v1/text/end-detect", json={"text": "Are you ready?"})
        agent = await client.post("/api/v1/agent/respond", json={"text": "Hello."})
        tts = await client.post("/api/v1/tts/synthesize", json={"text": "Hello."})
        artifact = await client.get(tts.json()["audio_url"])

    assert asr.json()["text"].startswith("Development transcript")
    assert corrected.json() == {"text": "Hello agent."}
    assert endpoint.json() == {"complete": True, "reason": "terminal_punctuation"}
    assert agent.json()["text"] == "Development response: I heard “Hello.”"
    assert tts.status_code == 200
    assert artifact.status_code == 200
    assert artifact.headers["content-type"] == "audio/wav"
    assert artifact.content[:4] == b"RIFF"
    assert artifact.content[8:12] == b"WAVE"


@pytest.mark.anyio
async def test_missing_session_uses_error_envelope(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/sessions/missing/turns", content=b"voice")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


@pytest.mark.anyio
async def test_separate_stage_failure_uses_stable_stage_error(tmp_path: Path) -> None:
    providers = ProviderSet(
        DevelopmentVAD(), FailedASR(), DevelopmentCorrection(), DevelopmentEndpoint(), DevelopmentAgent(), DevelopmentTTS()
    )
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"), providers=providers)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/audio/asr", content=wav_bytes(), headers={"content-type": "audio/wav"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "stage_failed"
    assert response.json()["error"]["stage"] == "asr"
    assert response.json()["error"]["retryable"] is True
    assert "development decoder failed" not in response.text


@pytest.mark.anyio
async def test_separate_stage_provider_does_not_block_event_loop(tmp_path: Path) -> None:
    heartbeat = asyncio.Event()
    slow = SlowASR(heartbeat)
    providers = ProviderSet(
        DevelopmentVAD(), slow, DevelopmentCorrection(), DevelopmentEndpoint(), DevelopmentAgent(), DevelopmentTTS()
    )
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"), providers=providers)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        asyncio.get_running_loop().call_later(0.03, heartbeat.set)
        operation = await client.post(
            "/api/v1/audio/asr", content=wav_bytes(), headers={"content-type": "audio/wav"}
        )
        assert operation.json() == {"text": "event loop remained responsive"}
        assert slow.heartbeat_seen_during_call is True


@pytest.mark.anyio
async def test_asr_and_full_turn_validate_wav_bounds_before_any_provider(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime", max_audio_bytes=1000)
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        session = (await client.post("/api/v1/sessions")).json()
        malformed = await client.post("/api/v1/audio/asr", content=b"not-wav", headers={"content-type": "audio/wav"})
        oversized = await client.post("/api/v1/audio/asr", content=wav_bytes(), headers={"content-type": "audio/wav"})
        wrong_type = await client.post("/api/v1/audio/asr", content=wav_bytes(), headers={"content-type": "application/octet-stream"})
        turn = await client.post(
            f"/api/v1/sessions/{session['id']}/turns", content=b"not-wav", headers={"content-type": "audio/wav"}
        )

    assert malformed.json()["error"]["code"] == "invalid_wav"
    assert oversized.json()["error"]["code"] == "audio_too_large"
    assert wrong_type.status_code == 415 and wrong_type.json()["error"]["code"] == "unsupported_media_type"
    assert turn.json()["error"]["code"] == "invalid_wav"


@pytest.mark.anyio
async def test_binary_endpoints_stop_streaming_as_soon_as_byte_limit_is_crossed(tmp_path: Path) -> None:
    limit = 64
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime", max_audio_bytes=limit)
    )
    session = await app.state.broker.create()
    speaker = app.state.speakers.create("Bounded")
    paths = (
        f"/api/v1/sessions/{session.id}/turns",
        "/api/v1/audio/vad",
        "/api/v1/audio/asr",
        f"/api/v1/speakers/{speaker.id}/samples",
        "/api/v1/speakers/match",
    )

    for path in paths:
        assert await post_oversized_first_chunk(app, path, limit) == (413, 1)


def test_streamed_binary_endpoints_keep_wav_request_body_in_openapi(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    document = app.openapi()
    paths = (
        "/api/v1/sessions/{session_id}/turns",
        "/api/v1/audio/vad",
        "/api/v1/audio/asr",
        "/api/v1/speakers/{speaker_id}/samples",
        "/api/v1/speakers/match",
    )

    for path in paths:
        schema = document["paths"][path]["post"]["requestBody"]["content"]["audio/wav"]["schema"]
        assert schema["type"] == "string"
        assert schema["format"] == "binary"
        assert "PCM WAV" in schema["description"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("payload", "settings_overrides", "expected_code"),
    [
        (b"not a wav", {}, "invalid_wav"),
        (unsupported_wav_bytes(), {}, "unsupported_wav"),
        (wav_bytes(), {"max_audio_bytes": 1_000}, "audio_too_large"),
        (wav_bytes(seconds=0.25), {"max_audio_seconds": 0.1}, "audio_too_long"),
    ],
)
async def test_tts_provider_output_must_be_bounded_pcm_wav_before_write(
    tmp_path: Path, payload: bytes, settings_overrides: dict[str, object], expected_code: str
) -> None:
    provider_set = ProviderSet(
        DevelopmentVAD(), FailedASR(), DevelopmentCorrection(), DevelopmentEndpoint(), DevelopmentAgent(), BytesTTS(payload)
    )
    settings = Settings(
        data_dir=tmp_path / expected_code / "data",
        runtime_dir=tmp_path / expected_code / "runtime",
        **settings_overrides,
    )
    app = create_app(settings, providers=provider_set)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/tts/synthesize", json={"text": "hello"})

    assert response.status_code in (400, 413, 415)
    assert response.json()["error"]["code"] == expected_code
    assert response.json()["error"]["stage"] == "tts"
    assert list((settings.runtime_dir / "artifacts").glob("*.wav")) == []


@pytest.mark.anyio
async def test_artifacts_are_private_revalidated_and_retained_with_a_bound(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime", max_artifacts=2
    )
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        urls = [(await client.post("/api/v1/tts/synthesize", json={"text": text})).json()["audio_url"] for text in ("a", "b", "c")]
        removed = await client.get(urls[0])
        kept = await client.get(urls[-1])
        kept_path = settings.runtime_dir / "artifacts" / urls[-1].rsplit("/", 1)[-1]
        kept_path.write_bytes(b"tampered")
        tampered = await client.get(urls[-1])

    assert removed.status_code == 404
    assert kept.status_code == 200
    assert stat.S_IMODE(kept_path.stat().st_mode) == 0o600
    assert len(list((settings.runtime_dir / "artifacts").glob("*.wav"))) == 2
    assert tampered.status_code == 400
    assert tampered.json()["error"]["code"] == "invalid_wav"
