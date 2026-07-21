import asyncio
import json

import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings
from agent_speak.realtime import RealtimeCoordinator
from tests.test_realtime import FakeASR, FakeText, FakeVAD


def websocket_scope(path: str) -> dict[str, object]:
    return {
        "type": "websocket",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("test", 1),
        "server": ("test", 80),
        "scheme": "ws",
        "root_path": "",
        "subprotocols": [],
        "state": {},
    }


@pytest.mark.anyio
async def test_realtime_socket_accepts_start_binary_and_stops_cleanly(tmp_path) -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
        realtime=coordinator,
    )
    session = await app.state.broker.create(speech_language="en")
    observed_languages: list[str] = []
    original_open = coordinator.open

    async def recording_open(session_id: str, speech_language: str):
        observed_languages.append(speech_language)
        return await original_open(session_id, speech_language)

    coordinator.open = recording_open  # type: ignore[method-assign]
    incoming: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    outgoing: list[dict[str, object]] = []
    await incoming.put({"type": "websocket.connect"})
    await incoming.put(
        {
            "type": "websocket.receive",
            "text": json.dumps(
                {
                    "type": "stream.start",
                    "format": "pcm_s16le",
                    "sample_rate": 16_000,
                    "channels": 1,
                    "frame_ms": 20,
                }
            ),
        }
    )
    await incoming.put({"type": "websocket.receive", "bytes": bytes(640)})
    await incoming.put({"type": "websocket.receive", "text": json.dumps({"type": "stream.stop"})})

    async def receive() -> dict[str, object]:
        return await incoming.get()

    async def send(message: dict[str, object]) -> None:
        outgoing.append(message)

    await app(
        websocket_scope(f"/api/v1/realtime/sessions/{session.id}"),  # type: ignore[arg-type]
        receive,
        send,
    )
    sent = [
        json.loads(item["text"])["type"]
        for item in outgoing
        if item["type"] == "websocket.send" and "text" in item
    ]
    assert "stream.accepted" in sent
    assert "stream.started" in sent
    assert "stream.stopped" in sent
    assert observed_languages == ["en"]
    await coordinator.close()


@pytest.mark.anyio
async def test_realtime_socket_rejects_binary_before_start(tmp_path) -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
        realtime=coordinator,
    )
    session = await app.state.broker.create()
    incoming: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    outgoing: list[dict[str, object]] = []
    await incoming.put({"type": "websocket.connect"})
    await incoming.put({"type": "websocket.receive", "bytes": bytes(640)})

    await app(
        websocket_scope(f"/api/v1/realtime/sessions/{session.id}"),  # type: ignore[arg-type]
        incoming.get,
        lambda message: _append(outgoing, message),
    )
    close = next(item for item in outgoing if item["type"] == "websocket.close")
    assert close["code"] == 4400
    await coordinator.close()


@pytest.mark.anyio
async def test_realtime_socket_rejects_unknown_session(tmp_path) -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
        realtime=coordinator,
    )
    incoming: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    outgoing: list[dict[str, object]] = []
    await incoming.put({"type": "websocket.connect"})
    await app(
        websocket_scope("/api/v1/realtime/sessions/missing"),  # type: ignore[arg-type]
        incoming.get,
        lambda message: _append(outgoing, message),
    )
    assert outgoing == [{"type": "websocket.close", "code": 4404, "reason": "Session not found"}]
    await coordinator.close()


async def _append(target: list[dict[str, object]], message: dict[str, object]) -> None:
    target.append(message)
