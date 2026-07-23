"""Continuous realtime speech orchestration with bounded shared workers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from inspect import signature
from typing import Any

from .concurrency import run_sync
from .config import Settings
from .diagnostic_logging import log_event
from .errors import PlatformError
from .model_ids import (
    ASRModelId,
    CorrectionModelId,
    DEFAULT_ASR_MODEL,
    DEFAULT_CORRECTION_MODEL,
)
from .realtime_audio import PCMContract, pcm16_to_wav
from .realtime_endpoint import DetectorAction, DetectorConfig, UtteranceDetector
from .realtime_models import CorrectionRevision, RealtimeEvent
from .realtime_queue import (
    ASRJob,
    ASRScheduler,
    QueueClosed,
    QueueFull,
    TextJob,
    TextScheduler,
)
from .transcripts import TranscriptLedger
from .speech_languages import SpeechLanguage
from .text_inference import ends_with_continuation


class RealtimeTextAdapter:
    """Joins existing endpoint/correction providers for local fallback mode."""

    def __init__(self, endpoint: Any, correction: Any) -> None:
        self.endpoint = endpoint
        self.correction = correction
        self._endpoint_accepts_language = len(signature(endpoint.detect).parameters) >= 2
        self._revision_accepts_language = (
            hasattr(correction, "revise")
            and len(signature(correction.revise).parameters) >= 3
        )

    def detect(
        self, text: str, speech_language: SpeechLanguage
    ) -> tuple[bool, str]:
        if self._endpoint_accepts_language:
            return self.endpoint.detect(text, speech_language)
        return self.endpoint.detect(text)

    def revise(
        self,
        previous: str,
        current: str,
        speech_language: SpeechLanguage,
    ) -> CorrectionRevision:
        if hasattr(self.correction, "revise"):
            if self._revision_accepts_language:
                return self.correction.revise(previous, current, speech_language)
            return self.correction.revise(previous, current)
        revised_previous = self.correction.correct(previous) if previous else ""
        revised_current = self.correction.correct(current)
        return CorrectionRevision(
            revised_previous,
            revised_current,
            (revised_previous, revised_current) != (previous, current),
        )


class RealtimeCoordinator:
    def __init__(
        self,
        settings: Settings,
        *,
        vad: Any,
        asr: Any,
        text: Any,
        broker: Any | None = None,
        model_control: Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings
        self.vad = vad
        self.asr = asr
        self.text = text
        self.broker = broker
        self.model_control = model_control
        self.logger = logger or logging.getLogger("agent_speak.diagnostic.disabled")
        self.asr_queue = ASRScheduler(
            max_finals=settings.realtime_final_queue,
            max_partials=settings.realtime_partial_queue,
        )
        self.text_queue = TextScheduler(
            max_endpoints=settings.realtime_text_queue,
            max_corrections=settings.realtime_text_queue,
        )
        self._streams: dict[str, RealtimeStream] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._started = False
        self._closed = False

    @classmethod
    def for_test(cls, *, vad: Any, asr: Any, text: Any) -> "RealtimeCoordinator":
        return cls(Settings(), vad=vad, asr=asr, text=text)

    async def start(self) -> None:
        if self._started:
            return
        if self._closed:
            raise RuntimeError("realtime coordinator is closed")
        self._started = True
        self._retain(self._asr_loop())
        self._retain(self._text_loop())

    async def open(
        self,
        session_id: str,
        speech_language: SpeechLanguage,
        asr_model: ASRModelId = DEFAULT_ASR_MODEL,
        correction_model: CorrectionModelId = DEFAULT_CORRECTION_MODEL,
    ) -> "RealtimeStream":
        await self.start()
        if session_id in self._streams:
            stream = self._streams[session_id]
            if stream.speech_language != speech_language:
                raise RuntimeError("realtime session language mismatch")
            if stream.asr_model != asr_model or stream.correction_model != correction_model:
                raise RuntimeError("realtime session model mismatch")
            return stream
        if len(self._streams) >= self.settings.max_sessions:
            raise PlatformError(
                "realtime_capacity",
                "Realtime session capacity is full",
                status_code=429,
                stage="asr",
                retryable=True,
            )
        if self.model_control is not None:
            await run_sync(self.model_control.acquire, session_id, asr_model)
        stream = RealtimeStream(
            self,
            session_id,
            speech_language,
            asr_model,
            correction_model,
        )
        self._streams[session_id] = stream
        log_event(
            self.logger,
            logging.INFO,
            "realtime.session.opened",
            session_id=session_id,
            stage="asr",
            model=asr_model,
            state="listening",
        )
        return stream

    async def release_lease(self, session_id: str) -> None:
        if self.model_control is not None:
            await run_sync(self.model_control.release, session_id)

    async def close_stream(self, session_id: str, reason: str = "user") -> None:
        stream = self._streams.pop(session_id, None)
        if stream is not None:
            await stream.stop(reason)
            log_event(
                self.logger,
                logging.INFO,
                "realtime.session.closed",
                session_id=session_id,
                stage="asr",
                model=stream.asr_model,
                state="stopped",
            )

    async def close(self) -> None:
        if self._closed:
            return
        for stream in list(self._streams.values()):
            await stream.stop("coordinator_shutdown")
        self._streams.clear()
        await self.asr_queue.close()
        await self.text_queue.close()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._closed = True

    def _retain(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _asr_loop(self) -> None:
        while True:
            try:
                job = await self.asr_queue.get()
            except QueueClosed:
                return
            stream = self._streams.get(job.session_id)
            if stream is None:
                continue
            error: Exception | None = None
            text = ""
            attempts = 2 if job.mode == "final" else 1
            for _ in range(attempts):
                try:
                    wav = pcm16_to_wav(job.pcm, sample_rate=16_000)
                    text = await run_sync(
                        self.asr.transcribe_mode,
                        wav,
                        job.mode,
                        job.speech_language,
                        job.asr_model,
                        job.session_id,
                    )
                    error = None
                    break
                except Exception as exc:
                    error = exc
            if error is not None:
                log_event(
                    self.logger,
                    logging.WARNING,
                    "realtime.asr.failed",
                    session_id=job.session_id,
                    stage="asr",
                    model=job.asr_model,
                    mode=job.mode,
                    error_code=getattr(error, "code", "asr_failed"),
                    retry=attempts,
                    error=error.__cause__ or error,
                )
            try:
                await stream._accept_asr_result(job, text, error)
            finally:
                stream._work_done()

    async def _text_loop(self) -> None:
        while True:
            try:
                job = await self.text_queue.get()
            except QueueClosed:
                return
            stream = self._streams.get(job.session_id)
            if stream is None:
                continue
            result: Any = None
            error: Exception | None = None
            try:
                if job.mode == "endpoint":
                    result = await asyncio.wait_for(
                        run_sync(
                            self.text.detect,
                            job.current_text,
                            job.speech_language,
                        ),
                        timeout=self.settings.realtime_endpoint_timeout_ms / 1_000,
                    )
                elif job.correction_model == "disabled":
                    result = CorrectionRevision(
                        job.previous_text,
                        job.current_text,
                        False,
                    )
                else:
                    result = await run_sync(
                        self.text.revise,
                        job.previous_text,
                        job.current_text,
                        job.speech_language,
                    )
            except Exception as exc:
                error = exc
            try:
                await stream._accept_text_result(job, result, error)
            finally:
                stream._work_done()


class RealtimeStream:
    def __init__(
        self,
        coordinator: RealtimeCoordinator,
        session_id: str,
        speech_language: SpeechLanguage,
        asr_model: ASRModelId,
        correction_model: CorrectionModelId,
    ) -> None:
        self.coordinator = coordinator
        self.settings = coordinator.settings
        self.session_id = session_id
        self.speech_language = speech_language
        self.asr_model = asr_model
        self.correction_model = correction_model
        self.state = "ready"
        self.contract = PCMContract(16_000, 1, self.settings.realtime_frame_ms)
        self.detector = UtteranceDetector(
            DetectorConfig(
                frame_ms=self.settings.realtime_frame_ms,
                pre_roll_ms=self.settings.realtime_pre_roll_ms,
                min_speech_ms=self.settings.realtime_min_speech_ms,
                endpoint_ms=self.settings.realtime_endpoint_ms,
                hard_endpoint_ms=self.settings.realtime_hard_endpoint_ms,
                max_utterance_ms=int(self.settings.realtime_max_utterance_seconds * 1_000),
            )
        )
        self.ledger = TranscriptLedger()
        self.history: list[RealtimeEvent] = []
        self._events: asyncio.Queue[RealtimeEvent | None] = asyncio.Queue(
            maxsize=self.settings.max_event_queue
        )
        self._sequence = 0
        self._utterance_id: str | None = None
        self._current_pcm = bytearray()
        self._partial_elapsed_ms = 0
        self._partial_generation = 0
        self._latest_partial_generation: dict[str, int] = {}
        self._pending = 0
        self._idle = asyncio.Event()
        self._idle.set()
        self._stopping = False
        self._lease_released = False

    async def start(self) -> None:
        if self.state == "listening":
            return
        if self.state == "stopped":
            self.detector.reset()
            self.coordinator.vad.reset()
            self._stopping = False
        self.state = "listening"
        await self._emit("stream.started")

    async def accept_pcm(self, frame: bytes) -> None:
        if self.state != "listening":
            raise PlatformError("stream_not_started", "Realtime stream is not listening", stage="vad")
        frame = self.contract.validate(frame)
        active_before = self._utterance_id is not None
        if active_before:
            self._current_pcm.extend(frame)
            self._partial_elapsed_ms += self.settings.realtime_frame_ms
        voiced = self.coordinator.vad.score(frame) >= 0.5
        actions = self.detector.accept(frame, voiced=voiced)
        for action in actions:
            await self._handle_detector_action(action)
        if self._utterance_id is not None and self._partial_elapsed_ms >= self.settings.realtime_partial_interval_ms:
            self._partial_elapsed_ms = 0
            await self._queue_partial()
        await asyncio.sleep(0)

    async def stop(self, reason: str = "user") -> None:
        if self.state == "stopped" or self._stopping:
            return
        self._stopping = True
        try:
            if self._utterance_id is not None and self._current_pcm:
                utterance_id = self._utterance_id
                pcm = bytes(self._current_pcm)
                self.detector.reset()
                self._clear_utterance()
                await self._queue_final(utterance_id, pcm)
            await self.wait_idle()
            self.ledger.finalize()
            self.detector.reset()
            self.coordinator.vad.reset()
            self.state = "stopped"
            await self._emit("stream.stopped", data={"reason": reason})
            with suppress(asyncio.QueueFull):
                self._events.put_nowait(None)
        finally:
            if not self._lease_released:
                await self.coordinator.release_lease(self.session_id)
                self._lease_released = True

    async def wait_idle(self) -> None:
        await self._idle.wait()

    async def events(self) -> AsyncIterator[RealtimeEvent]:
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event

    async def _handle_detector_action(self, action: DetectorAction) -> None:
        if action.kind == "speech_started":
            self._utterance_id = action.utterance_id
            self._current_pcm = bytearray(action.pcm)
            self._partial_elapsed_ms = 0
            await self._emit("vad.speech_started", utterance_id=action.utterance_id)
        elif action.kind == "endpoint_candidate":
            await self._emit(
                "endpoint.candidate",
                utterance_id=action.utterance_id,
                data={"silence_ms": action.silence_ms},
            )
            rows = self.ledger.rows()
            current_text = rows[-1].text if rows and rows[-1].utterance_id == action.utterance_id else ""
            await self._queue_text(
                TextJob(
                    self.session_id,
                    action.utterance_id,
                    "endpoint",
                    "",
                    current_text,
                    self.speech_language,
                    self.correction_model,
                )
            )
        elif action.kind == "endpoint_cancelled":
            await self._emit("endpoint.cancelled", utterance_id=action.utterance_id)
        elif action.kind == "utterance_final":
            await self._queue_final(action.utterance_id, action.pcm)
            self._clear_utterance()

    async def _queue_partial(self) -> None:
        assert self._utterance_id is not None
        self._partial_generation += 1
        generation = self._partial_generation
        self._latest_partial_generation[self._utterance_id] = generation
        job = ASRJob(
            self.session_id,
            self._utterance_id,
            generation,
            "partial",
            bytes(self._current_pcm),
            self.speech_language,
            self.asr_model,
        )
        try:
            inserted = await self.coordinator.asr_queue.put_partial(job)
        except QueueFull:
            await self._emit(
                "pipeline.warning",
                utterance_id=self._utterance_id,
                data={"code": "partial_queue_full"},
            )
            return
        if inserted:
            self._work_queued()
        await self._emit("asr.queued", utterance_id=self._utterance_id, data={"mode": "partial"})

    async def _queue_final(self, utterance_id: str, pcm: bytes) -> None:
        job = ASRJob(
            self.session_id,
            utterance_id,
            1,
            "final",
            pcm,
            self.speech_language,
            self.asr_model,
        )
        try:
            await self.coordinator.asr_queue.put_final(job)
        except QueueFull:
            await self._emit(
                "pipeline.warning",
                utterance_id=utterance_id,
                data={"code": "final_queue_full"},
            )
            self.state = "paused"
            return
        self._work_queued()
        await self._emit("asr.queued", utterance_id=utterance_id, data={"mode": "final"})

    async def _queue_text(self, job: TextJob) -> None:
        try:
            if job.mode == "endpoint":
                await self.coordinator.text_queue.put_endpoint(job)
            else:
                await self.coordinator.text_queue.put_correction(job)
        except QueueFull:
            await self._emit(
                "pipeline.warning",
                utterance_id=job.utterance_id,
                data={"code": f"{job.mode}_queue_full"},
            )
            if job.mode == "endpoint":
                action = self.detector.finalize_candidate()
                if action is not None:
                    await self._handle_detector_action(action)
            else:
                await self._complete_utterance(job.utterance_id)
            return
        self._work_queued()

    async def _accept_asr_result(
        self,
        job: ASRJob,
        text: str,
        error: Exception | None,
    ) -> None:
        if error is not None:
            await self._emit(
                "pipeline.warning",
                utterance_id=job.utterance_id,
                data={"code": "asr_failed", "mode": job.mode},
            )
            if job.mode == "final":
                await self._complete_utterance(job.utterance_id)
            return
        if job.mode == "partial":
            if self._latest_partial_generation.get(job.utterance_id) != job.generation:
                return
            try:
                self.ledger.accept_partial(job.utterance_id, text)
            except PlatformError:
                return
            await self._emit("asr.partial", utterance_id=job.utterance_id, data={"text": text})
            return

        self.ledger.accept_final(job.utterance_id, text)
        await self._emit(
            "asr.final",
            utterance_id=job.utterance_id,
            data={"text": text, "asr_model": self.asr_model},
        )
        rows = self.ledger.rows()
        previous = rows[-2].text if len(rows) > 1 else ""
        await self._emit(
            "correction.processing",
            utterance_id=job.utterance_id,
            data={"policy": self.correction_model},
        )
        await self._queue_text(
            TextJob(
                self.session_id,
                job.utterance_id,
                "correction",
                previous,
                text,
                self.speech_language,
                self.correction_model,
            )
        )

    async def _accept_text_result(
        self,
        job: TextJob,
        result: Any,
        error: Exception | None,
    ) -> None:
        if job.mode == "endpoint":
            complete = True
            reason = "fallback_complete"
            # The endpoint candidate can outrun partial ASR on a busy worker.
            # Never treat an empty snapshot as semantic evidence that speech is
            # complete; extend to the hard endpoint while ASR catches up.
            if not job.current_text.strip():
                complete, reason = False, "awaiting_asr"
            elif error is None and isinstance(result, tuple) and len(result) == 2:
                complete, reason = bool(result[0]), str(result[1])
            elif ends_with_continuation(job.current_text, job.speech_language):
                complete, reason = False, "continuation_marker"
            if complete:
                action = self.detector.finalize_candidate()
                if action is not None:
                    await self._handle_detector_action(action)
            elif self.detector.extend_endpoint():
                await self._emit(
                    "endpoint.extended",
                    utterance_id=job.utterance_id,
                    data={"reason": reason},
                )
            return

        if error is not None or not isinstance(result, CorrectionRevision):
            await self._emit(
                "pipeline.warning",
                utterance_id=job.utterance_id,
                data={"code": "correction_failed"},
            )
            await self._complete_utterance(job.utterance_id)
            return
        try:
            self.ledger.apply_revision(job.utterance_id, result)
        except PlatformError:
            return
        await self._emit(
            "transcript.revised",
            utterance_id=job.utterance_id,
            data={
                "previous_text": result.previous_text,
                "current_text": result.current_text,
                "changed": result.changed,
                "policy": job.correction_model,
            },
        )
        await self._complete_utterance(job.utterance_id)

    async def _complete_utterance(self, utterance_id: str) -> None:
        text = ""
        for row in reversed(self.ledger.rows()):
            if row.utterance_id == utterance_id:
                text = row.text
                break
        await self._emit(
            "utterance.completed",
            utterance_id=utterance_id,
            data={
                "text": text,
                "asr_model": self.asr_model,
                "correction_model": self.correction_model,
            },
        )
        if not self._stopping:
            self.state = "listening"

    def _clear_utterance(self) -> None:
        self._utterance_id = None
        self._current_pcm.clear()
        self._partial_elapsed_ms = 0

    def _work_queued(self) -> None:
        self._pending += 1
        self._idle.clear()

    def _work_done(self) -> None:
        self._pending = max(0, self._pending - 1)
        if self._pending == 0:
            self._idle.set()

    async def _emit(
        self,
        event_type: str,
        *,
        utterance_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self._sequence += 1
        event = RealtimeEvent(
            sequence=self._sequence,
            session_id=self.session_id,
            utterance_id=utterance_id,
            type=event_type,
            data=data or {},
        )
        self.history.append(event)
        if len(self.history) > self.settings.max_session_events:
            del self.history[: len(self.history) - self.settings.max_session_events]
        await self._events.put(event)
        if self.coordinator.broker is not None and event_type in {
            "asr.partial",
            "asr.final",
            "transcript.revised",
            "utterance.completed",
            "pipeline.warning",
        }:
            await self.coordinator.broker.emit(
                self.session_id,
                "realtime.event",
                data={
                    "utterance_id": utterance_id or "",
                    "realtime_type": event_type,
                    "text": str(event.data.get("text", "")),
                    "asr_model": self.asr_model,
                    "correction_model": self.correction_model,
                },
            )
