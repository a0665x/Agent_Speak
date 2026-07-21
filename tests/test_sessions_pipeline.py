from __future__ import annotations

import asyncio
import threading
import time
from contextlib import suppress
from pathlib import Path

import httpx
import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings
from agent_speak.errors import PlatformError
from agent_speak.pipeline import ProviderSet
from agent_speak.sessions import SessionBroker
from .audio_fixtures import wav_bytes


class Voice:
    def detect(self, audio: bytes) -> dict[str, object]:
        return {"voiced": bool(audio), "rms": 0.25, "duration_seconds": 0.1}


class Words:
    def transcribe(self, audio: bytes) -> str:
        return "hello platform"


class BrokenWords:
    def transcribe(self, audio: bytes) -> str:
        raise RuntimeError("decoder unavailable")


class UnavailableWords:
    def transcribe(self, audio: bytes) -> str:
        raise PlatformError(
            "provider_unavailable", "ASR provider unavailable", status_code=503, stage="asr", retryable=True
        )


class Polish:
    def correct(self, text: str) -> str:
        return "Hello platform."


class Endpoint:
    def detect(self, text: str) -> tuple[bool, str]:
        return True, "terminal_punctuation"


class Reply:
    def respond(self, text: str) -> str:
        return f"Acknowledged: {text}"


class Tone:
    def synthesize(self, text: str) -> bytes:
        return wav_bytes(frequency=660)


class BlockingWords:
    def __init__(self, heartbeat: threading.Event | None = None) -> None:
        self.heartbeat = heartbeat
        self.heartbeat_seen_during_call = False

    def transcribe(self, audio: bytes) -> str:
        time.sleep(0.15)
        if self.heartbeat is not None:
            self.heartbeat_seen_during_call = self.heartbeat.is_set()
        return "hello platform"


def providers(*, broken: bool = False) -> ProviderSet:
    return ProviderSet(
        vad=Voice(),
        asr=BrokenWords() if broken else Words(),
        correction=Polish(),
        endpoint=Endpoint(),
        agent=Reply(),
        tts=Tone(),
    )


def make_client(tmp_path: Path, *, broken: bool = False) -> tuple[httpx.AsyncClient, object]:
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
        providers=providers(broken=broken),
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return client, app


@pytest.mark.anyio
async def test_session_creation_and_get_include_ordered_history(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    async with client:
        created = await client.post("/api/v1/sessions")
        fetched = await client.get(f"/api/v1/sessions/{created.json()['id']}")

    assert created.status_code == 201
    assert fetched.status_code == 200
    assert fetched.json()["state"] == "ready"
    assert [event["sequence"] for event in fetched.json()["events"]] == [1]
    assert fetched.json()["events"][0]["type"] == "session.created"


@pytest.mark.anyio
@pytest.mark.parametrize("speech_language", ["auto", "en", "zh-TW", "ja", "ko"])
async def test_session_freezes_requested_speech_language(
    tmp_path: Path, speech_language: str
) -> None:
    client, _ = make_client(tmp_path)
    async with client:
        created = await client.post(
            "/api/v1/sessions", params={"speech_language": speech_language}
        )
        fetched = await client.get(f"/api/v1/sessions/{created.json()['id']}")

    assert created.status_code == 201
    assert created.json()["speech_language"] == speech_language
    assert fetched.json()["speech_language"] == speech_language
    assert fetched.json()["events"][0]["data"]["speech_language"] == speech_language


@pytest.mark.anyio
async def test_session_speech_language_defaults_to_traditional_chinese(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    async with client:
        created = await client.post("/api/v1/sessions")

    assert created.status_code == 201
    assert created.json()["speech_language"] == "zh-TW"
    assert created.json()["events"][0]["data"]["speech_language"] == "zh-TW"


@pytest.mark.anyio
async def test_session_rejects_unknown_speech_language_with_stable_validation_error(
    tmp_path: Path,
) -> None:
    client, _ = make_client(tmp_path)
    async with client:
        response = await client.post(
            "/api/v1/sessions", params={"speech_language": "fr"}
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["retryable"] is False


@pytest.mark.anyio
async def test_full_turn_runs_stages_in_order_and_records_timings(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    async with client:
        session = (await client.post("/api/v1/sessions")).json()
        turn = await client.post(
            f"/api/v1/sessions/{session['id']}/turns",
            content=wav_bytes(),
            headers={"content-type": "audio/wav"},
        )
        fetched = await client.get(f"/api/v1/sessions/{session['id']}")

    assert turn.status_code == 200
    assert turn.json()["transcript"] == "hello platform"
    assert turn.json()["corrected_text"] == "Hello platform."
    assert turn.json()["response"] == "Acknowledged: Hello platform."
    assert turn.json()["audio_url"].startswith("/api/v1/artifacts/")
    completed = [e for e in fetched.json()["events"] if e["type"] == "stage.completed"]
    assert [event["stage"] for event in completed] == ["vad", "asr", "correction", "endpoint", "agent", "tts"]
    assert all(event["elapsed_ms"] >= 0 for event in completed)
    sequences = [event["sequence"] for event in fetched.json()["events"]]
    assert sequences == list(range(1, len(sequences) + 1))
    assert fetched.json()["state"] == "completed"


@pytest.mark.anyio
async def test_pipeline_failure_has_stage_error_and_failure_event(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, broken=True)
    async with client:
        session = (await client.post("/api/v1/sessions")).json()
        failed = await client.post(
            f"/api/v1/sessions/{session['id']}/turns", content=wav_bytes(), headers={"content-type": "audio/wav"}
        )
        fetched = await client.get(f"/api/v1/sessions/{session['id']}")

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "stage_failed"
    assert failed.json()["error"]["stage"] == "asr"
    assert failed.json()["error"]["retryable"] is True
    assert fetched.json()["state"] == "failed"
    assert fetched.json()["events"][-1]["type"] == "pipeline.failed"
    assert fetched.json()["events"][-1]["stage"] == "asr"
    assert "decoder unavailable" not in failed.text
    assert "decoder unavailable" not in str(fetched.json()["events"])


@pytest.mark.anyio
async def test_provider_platform_error_also_emits_stage_failed(tmp_path: Path) -> None:
    provider_set = providers()
    provider_set.asr = UnavailableWords()
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"), providers=provider_set
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        session = (await client.post("/api/v1/sessions")).json()
        failed = await client.post(
            f"/api/v1/sessions/{session['id']}/turns",
            content=wav_bytes(),
            headers={"content-type": "audio/wav"},
        )
        events = (await client.get(f"/api/v1/sessions/{session['id']}")).json()["events"]

    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "provider_unavailable"
    assert [(event["type"], event["stage"], event["data"].get("code")) for event in events[-2:]] == [
        ("stage.failed", "asr", "provider_unavailable"),
        ("pipeline.failed", "asr", "provider_unavailable"),
    ]


@pytest.mark.anyio
async def test_blocking_provider_does_not_starve_event_loop(tmp_path: Path) -> None:
    heartbeat = threading.Event()
    blocking = BlockingWords(heartbeat)
    provider_set = providers()
    provider_set.asr = blocking
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"), providers=provider_set
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        session = (await client.post("/api/v1/sessions")).json()
        asyncio.get_running_loop().call_later(0.03, heartbeat.set)
        turn = await client.post(
            f"/api/v1/sessions/{session['id']}/turns",
            content=wav_bytes(),
            headers={"content-type": "audio/wav"},
        )
        assert turn.status_code == 200
        assert blocking.heartbeat_seen_during_call is True


@pytest.mark.anyio
async def test_concurrent_turn_for_same_session_has_stable_conflict(tmp_path: Path) -> None:
    provider_set = providers()
    provider_set.asr = BlockingWords()
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"), providers=provider_set
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        session = (await client.post("/api/v1/sessions")).json()
        path = f"/api/v1/sessions/{session['id']}/turns"
        first = asyncio.create_task(client.post(path, content=wav_bytes(), headers={"content-type": "audio/wav"}))
        second_task = asyncio.create_task(client.post(path, content=wav_bytes(), headers={"content-type": "audio/wav"}))
        first_response, second = await asyncio.gather(first, second_task)

    assert first_response.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"] == {
        "code": "turn_in_progress",
        "message": "A turn is already in progress for this session",
        "stage": None,
        "retryable": True,
        "details": {},
    }


@pytest.mark.anyio
async def test_broker_subscription_replays_history_then_streams_new_events() -> None:
    broker = SessionBroker()
    session = await broker.create()
    subscription = broker.subscribe(session.id)

    first = await anext(subscription)
    await broker.emit(session.id, "pipeline.started")
    second = await anext(subscription)
    await subscription.aclose()

    assert (first.sequence, first.type) == (1, "session.created")
    assert (second.sequence, second.type) == (2, "pipeline.started")


@pytest.mark.anyio
async def test_broker_bounds_sessions_history_and_slow_subscriber_queue() -> None:
    broker = SessionBroker(max_sessions=2, max_events=3, subscriber_queue_size=1)
    oldest = await broker.create()
    await broker.create()
    current = await broker.create()

    with pytest.raises(PlatformError) as removed:
        broker.get(oldest.id)
    assert removed.value.code == "session_not_found"

    await broker.emit(current.id, "event.2")
    await broker.emit(current.id, "event.3")
    await broker.emit(current.id, "event.4")
    assert [(event.sequence, event.type) for event in broker.get(current.id).events] == [
        (2, "event.2"),
        (3, "event.3"),
        (4, "event.4"),
    ]

    subscription = broker.subscribe(current.id)
    for _ in range(3):
        await anext(subscription)
    await broker.emit(current.id, "queued.old")
    await broker.emit(current.id, "queued.latest")
    assert (await anext(subscription)).type == "queued.latest"
    await subscription.aclose()


@pytest.mark.anyio
async def test_websocket_route_accepts_and_replays_ordered_history(tmp_path: Path) -> None:
    _, app = make_client(tmp_path)
    session = await app.state.broker.create()
    incoming: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    await incoming.put({"type": "websocket.connect"})
    outgoing: list[dict[str, object]] = []
    event_sent = asyncio.Event()

    async def receive() -> dict[str, object]:
        return await incoming.get()

    async def send(message: dict[str, object]) -> None:
        outgoing.append(message)
        if message["type"] == "websocket.send":
            event_sent.set()

    scope = {
        "type": "websocket", "asgi": {"version": "3.0", "spec_version": "2.4"}, "http_version": "1.1",
        "scheme": "ws", "path": f"/api/v1/sessions/{session.id}/events", "raw_path": b"", "query_string": b"",
        "root_path": "", "headers": [], "client": ("test", 1), "server": ("test", 80), "subprotocols": [], "state": {},
    }
    task = asyncio.create_task(app(scope, receive, send))
    await asyncio.wait_for(event_sent.wait(), timeout=1)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert outgoing[0]["type"] == "websocket.accept"
    assert outgoing[1]["type"] == "websocket.send"
    assert outgoing[1]["text"].find('"sequence":1') > 0
    assert outgoing[1]["text"].find('"type":"session.created"') > 0
