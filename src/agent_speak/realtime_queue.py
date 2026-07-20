"""Bounded priority schedulers for realtime inference work."""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Literal


class QueueFull(RuntimeError):
    pass


class QueueClosed(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ASRJob:
    session_id: str
    utterance_id: str
    generation: int
    mode: Literal["partial", "final"]
    pcm: bytes


@dataclass(frozen=True, slots=True)
class TextJob:
    session_id: str
    utterance_id: str
    mode: Literal["endpoint", "correction"]
    previous_text: str
    current_text: str


class ASRScheduler:
    def __init__(self, *, max_finals: int, max_partials: int) -> None:
        self._max_finals = max_finals
        self._max_partials = max_partials
        self._finals: deque[ASRJob] = deque()
        self._partials: OrderedDict[tuple[str, str], ASRJob] = OrderedDict()
        self._condition = asyncio.Condition()
        self._closed = False

    @property
    def depths(self) -> dict[str, int]:
        return {"final": len(self._finals), "partial": len(self._partials)}

    async def put_final(self, job: ASRJob) -> None:
        if job.mode != "final":
            raise ValueError("put_final requires a final ASR job")
        async with self._condition:
            self._ensure_open()
            if len(self._finals) >= self._max_finals:
                raise QueueFull("final ASR queue is full")
            self._finals.append(job)
            self._condition.notify()

    async def put_partial(self, job: ASRJob) -> None:
        if job.mode != "partial":
            raise ValueError("put_partial requires a partial ASR job")
        key = (job.session_id, job.utterance_id)
        async with self._condition:
            self._ensure_open()
            if key not in self._partials and len(self._partials) >= self._max_partials:
                raise QueueFull("partial ASR queue is full")
            self._partials[key] = job
            self._condition.notify()

    async def get(self) -> ASRJob:
        async with self._condition:
            await self._condition.wait_for(self._has_work_or_closed)
            if self._finals:
                return self._finals.popleft()
            if self._partials:
                _, job = self._partials.popitem(last=False)
                return job
            raise QueueClosed("ASR scheduler is closed")

    async def close(self) -> None:
        async with self._condition:
            self._closed = True
            self._condition.notify_all()

    def _ensure_open(self) -> None:
        if self._closed:
            raise QueueClosed("ASR scheduler is closed")

    def _has_work_or_closed(self) -> bool:
        return bool(self._finals or self._partials or self._closed)


class TextScheduler:
    def __init__(self, *, max_endpoints: int, max_corrections: int) -> None:
        self._max_endpoints = max_endpoints
        self._max_corrections = max_corrections
        self._endpoints: deque[TextJob] = deque()
        self._corrections: deque[TextJob] = deque()
        self._condition = asyncio.Condition()
        self._closed = False

    @property
    def depths(self) -> dict[str, int]:
        return {"endpoint": len(self._endpoints), "correction": len(self._corrections)}

    async def put_endpoint(self, job: TextJob) -> None:
        if job.mode != "endpoint":
            raise ValueError("put_endpoint requires an endpoint text job")
        async with self._condition:
            self._ensure_open()
            if len(self._endpoints) >= self._max_endpoints:
                raise QueueFull("endpoint text queue is full")
            self._endpoints.append(job)
            self._condition.notify()

    async def put_correction(self, job: TextJob) -> None:
        if job.mode != "correction":
            raise ValueError("put_correction requires a correction text job")
        async with self._condition:
            self._ensure_open()
            if len(self._corrections) >= self._max_corrections:
                raise QueueFull("correction text queue is full")
            self._corrections.append(job)
            self._condition.notify()

    async def get(self) -> TextJob:
        async with self._condition:
            await self._condition.wait_for(self._has_work_or_closed)
            if self._endpoints:
                return self._endpoints.popleft()
            if self._corrections:
                return self._corrections.popleft()
            raise QueueClosed("text scheduler is closed")

    async def close(self) -> None:
        async with self._condition:
            self._closed = True
            self._condition.notify_all()

    def _ensure_open(self) -> None:
        if self._closed:
            raise QueueClosed("text scheduler is closed")

    def _has_work_or_closed(self) -> bool:
        return bool(self._endpoints or self._corrections or self._closed)
