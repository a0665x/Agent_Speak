"""Binary WebSocket transport for realtime PCM streams."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from .errors import PlatformError
from .realtime_models import SessionPing, StreamStart, StreamStop


def register_realtime_routes(app: FastAPI) -> None:
    @app.websocket("/api/v1/realtime/sessions/{session_id}")
    async def realtime_socket(websocket: WebSocket, session_id: str) -> None:
        try:
            session = app.state.broker.get(session_id)
        except PlatformError:
            await websocket.close(code=4404, reason="Session not found")
            return
        try:
            stream = await app.state.realtime.open(
                session_id,
                session.speech_language,
                session.asr_model,
                session.correction_model,
            )
        except PlatformError:
            await websocket.close(code=4429, reason="Realtime capacity is full")
            return

        await websocket.accept()
        sender = asyncio.create_task(_send_events(websocket, stream))
        started = False
        transport_closed = False
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    if not started:
                        await websocket.close(code=4400, reason="stream.start is required")
                        transport_closed = True
                        break
                    try:
                        await stream.accept_pcm(message["bytes"])
                    except PlatformError as exc:
                        await websocket.close(code=4400, reason=exc.code)
                        transport_closed = True
                        break
                    continue

                raw = message.get("text")
                if raw is None:
                    await websocket.close(code=4400, reason="Invalid realtime frame")
                    transport_closed = True
                    break
                try:
                    payload = json.loads(raw)
                    message_type = payload.get("type")
                    if message_type == "stream.start":
                        control = StreamStart.model_validate(payload)
                        if started or control.frame_ms != stream.contract.frame_ms:
                            raise ValueError("unsupported or duplicate stream.start")
                        await stream._emit(
                            "stream.accepted",
                            data={
                                "format": control.format,
                                "sample_rate": control.sample_rate,
                                "channels": control.channels,
                                "frame_ms": control.frame_ms,
                            },
                        )
                        await stream.start()
                        started = True
                    elif message_type == "stream.stop":
                        StreamStop.model_validate(payload)
                        await stream.stop("user")
                        break
                    elif message_type == "session.ping":
                        ping = SessionPing.model_validate(payload)
                        await stream._emit("session.pong", data={"nonce": ping.nonce})
                    else:
                        raise ValueError("unknown realtime control")
                except (json.JSONDecodeError, TypeError, ValueError, ValidationError):
                    await websocket.close(code=4400, reason="Invalid realtime control")
                    transport_closed = True
                    break
        except WebSocketDisconnect:
            pass
        except Exception:
            if not transport_closed:
                with suppress(RuntimeError):
                    await websocket.close(code=4500, reason="Realtime transport failed")
                transport_closed = True
        finally:
            await app.state.realtime.close_stream(session_id, "disconnect")
            if transport_closed:
                sender.cancel()
            try:
                await asyncio.wait_for(sender, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                sender.cancel()
                with suppress(asyncio.CancelledError):
                    await sender


async def _send_events(websocket: WebSocket, stream: object) -> None:
    try:
        async for event in stream.events():  # type: ignore[attr-defined]
            await websocket.send_json(event.model_dump(mode="json"))
    except (RuntimeError, WebSocketDisconnect):
        return
