"""In-memory session state and ordered event fan-out."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import uuid4

from .errors import PlatformError
from .schemas import PipelineEvent, SessionSummary
from .speech_languages import DEFAULT_SPEECH_LANGUAGE, SpeechLanguage


class SessionBroker:
    def __init__(self, *, max_sessions: int = 100, max_events: int = 128, subscriber_queue_size: int = 64) -> None:
        self.max_sessions = max_sessions
        self.max_events = max_events
        self.subscriber_queue_size = subscriber_queue_size
        self._sessions: dict[str, SessionSummary] = {}
        self._subscribers: dict[str, set[asyncio.Queue[PipelineEvent]]] = {}
        self._sequences: dict[str, int] = {}
        self._active_turns: set[str] = set()
        self._lock = asyncio.Lock()

    async def create(
        self, *, speech_language: SpeechLanguage = DEFAULT_SPEECH_LANGUAGE
    ) -> SessionSummary:
        session = SessionSummary(
            id=uuid4().hex,
            state="ready",
            speech_language=speech_language,
            created_at=datetime.now(timezone.utc),
        )
        async with self._lock:
            if len(self._sessions) >= self.max_sessions:
                removable = next(
                    (
                        identifier
                        for identifier in self._sessions
                        if identifier not in self._active_turns and not self._subscribers[identifier]
                    ),
                    None,
                )
                if removable is None:
                    raise PlatformError(
                        "session_capacity_reached",
                        "Session capacity has been reached",
                        status_code=503,
                        retryable=True,
                    )
                del self._sessions[removable]
                del self._subscribers[removable]
                del self._sequences[removable]
            self._sessions[session.id] = session
            self._subscribers[session.id] = set()
            self._sequences[session.id] = 0
        await self.emit(
            session.id,
            "session.created",
            data={"state": "ready", "speech_language": speech_language},
        )
        return session

    def get(self, session_id: str) -> SessionSummary:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise PlatformError("session_not_found", "Session not found", status_code=404) from exc

    async def set_state(self, session_id: str, state: str) -> None:
        async with self._lock:
            self.get(session_id).state = state

    @asynccontextmanager
    async def admit_turn(self, session_id: str) -> AsyncIterator[None]:
        async with self._lock:
            self.get(session_id)
            if session_id in self._active_turns:
                raise PlatformError(
                    "turn_in_progress",
                    "A turn is already in progress for this session",
                    status_code=409,
                    retryable=True,
                )
            self._active_turns.add(session_id)
        try:
            yield
        finally:
            async with self._lock:
                self._active_turns.discard(session_id)

    async def emit(
        self,
        session_id: str,
        event_type: str,
        *,
        stage: str | None = None,
        elapsed_ms: float | None = None,
        data: dict[str, object] | None = None,
    ) -> PipelineEvent:
        async with self._lock:
            session = self.get(session_id)
            sequence = self._sequences[session_id] + 1
            self._sequences[session_id] = sequence
            event = PipelineEvent(
                sequence=sequence,
                type=event_type,
                stage=stage,
                elapsed_ms=elapsed_ms,
                data=data or {},
            )
            session.events.append(event)
            if len(session.events) > self.max_events:
                del session.events[: len(session.events) - self.max_events]
            subscribers = tuple(self._subscribers[session_id])
        for queue in subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)
        return event

    async def subscribe(self, session_id: str) -> AsyncIterator[PipelineEvent]:
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue(maxsize=self.subscriber_queue_size)
        async with self._lock:
            session = self.get(session_id)
            history = tuple(session.events)
            self._subscribers[session_id].add(queue)
        try:
            for event in history:
                yield event
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers.get(session_id, set()).discard(queue)
