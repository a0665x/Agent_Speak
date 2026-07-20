"""Sequential full-turn orchestration with per-stage events and timings."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from time import perf_counter
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from .development import (
    DevelopmentASR,
    DevelopmentAgent,
    DevelopmentCorrection,
    DevelopmentEndpoint,
    DevelopmentTTS,
    DevelopmentVAD,
)
from .errors import PlatformError
from .concurrency import run_sync
from .audio import decode_wav
from .schemas import TurnResponse
from .sessions import SessionBroker
from .providers import (
    ASRProvider, AgentProvider, CorrectionProvider, DEFAULT_CAPABILITIES, EndpointProvider, TTSProvider, VADProvider
)
from .schemas import ProviderCapability
from .production import FasterWhisperASR, PiperTTS
from .text_inference import LlamaCppTextProvider


@dataclass(slots=True)
class ProviderSet:
    vad: VADProvider
    asr: ASRProvider
    correction: CorrectionProvider
    endpoint: EndpointProvider
    agent: AgentProvider
    tts: TTSProvider
    capability_metadata: list[ProviderCapability] | None = None
    capability_factory: Callable[[], list[ProviderCapability]] | None = None

    @classmethod
    def configured(cls, settings: Any, *, vad: Any | None = None) -> "ProviderSet":
        asr = FasterWhisperASR(
            model_name=settings.asr_model,
            language=settings.asr_language,
            accelerator=settings.accelerator,
            cpu_compute_type=settings.asr_compute_type,
            cuda_compute_type=settings.asr_cuda_compute_type,
            cpu_threads=settings.asr_cpu_threads,
        )
        tts = PiperTTS(model_path=settings.tts_model_path)
        text_worker: LlamaCppTextProvider | None = None
        if settings.correction_worker_url:
            text_worker = LlamaCppTextProvider(
                settings.correction_worker_url,
                settings.correction_model,
                device=settings.effective_accelerator,
            )
            correction_provider: CorrectionProvider = text_worker
            endpoint_provider: EndpointProvider = text_worker
        else:
            correction_provider = DevelopmentCorrection()
            endpoint_provider = DevelopmentEndpoint()

        def configured_capabilities() -> list[ProviderCapability]:
            asr_ready = asr.is_ready()
            tts_ready = tts.model_path.is_file() and tts.config_path.is_file()
            text_ready = text_worker.is_ready() if text_worker is not None else True
            device_label = "CUDA inference." if asr.device == "cuda" else "CPU inference."
            asr_limitations = [f"Faster-Whisper local transcription; {device_label}"]
            if asr.fallback_reason:
                asr_limitations.append(f"Automatic CPU fallback: {asr.fallback_reason}")
            return [
                ProviderCapability(stage="vad", name="energy-vad", ready=True, development=False, limitations=[]),
                ProviderCapability(
                    stage="asr", name=f"faster-whisper-{settings.asr_model}", ready=asr_ready, development=False,
                    limitations=(
                        asr_limitations
                        if asr_ready
                        else ["Model is not cached locally; the first transcription requires a successful model download."]
                    ),
                    device=asr.device,
                ),
                ProviderCapability(
                    stage="correction",
                    name=settings.correction_model if settings.correction_worker_url else DEFAULT_CAPABILITIES[2].name,
                    ready=text_ready,
                    development=not bool(settings.correction_worker_url),
                    limitations=[] if text_ready else ["Correction worker health probe failed."],
                    device=text_worker.device if text_worker is not None else "cpu",
                ),
                ProviderCapability(
                    stage="endpoint",
                    name=settings.correction_model if settings.correction_worker_url else DEFAULT_CAPABILITIES[3].name,
                    ready=text_ready,
                    development=not bool(settings.correction_worker_url),
                    limitations=[] if text_ready else ["Endpoint worker health probe failed."],
                    device=text_worker.device if text_worker is not None else "cpu",
                ),
                DEFAULT_CAPABILITIES[4],
                ProviderCapability(
                    stage="tts", name=f"piper-{tts.model_path.stem}", ready=tts_ready, development=False,
                    limitations=["Piper local speech synthesis."] if tts_ready else [f"Voice model missing: {tts.model_path}"],
                ),
            ]
        return cls(
            vad or DevelopmentVAD(), asr, correction_provider, endpoint_provider, DevelopmentAgent(), tts,
            capability_factory=configured_capabilities,
        )

    @classmethod
    def development(cls, *, vad: Any | None = None) -> "ProviderSet":
        return cls(
            vad or DevelopmentVAD(), DevelopmentASR(), DevelopmentCorrection(), DevelopmentEndpoint(), DevelopmentAgent(), DevelopmentTTS(),
            capability_metadata=list(DEFAULT_CAPABILITIES),
        )

    def capabilities(self) -> list[ProviderCapability]:
        if self.capability_factory is not None:
            return self.capability_factory()
        if self.capability_metadata is not None:
            return self.capability_metadata
        providers = {
            "vad": self.vad, "asr": self.asr, "correction": self.correction,
            "endpoint": self.endpoint, "agent": self.agent, "tts": self.tts,
        }
        return [
            ProviderCapability(
                stage=stage,
                name=provider.__class__.__name__,
                ready=True,
                development=provider.__class__.__module__ == "agent_speak.development",
                limitations=["Injected provider; consult deployment configuration for model limitations."],
            )
            for stage, provider in providers.items()
        ]


class Pipeline:
    stages = ("vad", "asr", "correction", "endpoint", "agent", "tts")

    def __init__(
        self,
        broker: SessionBroker,
        providers: ProviderSet,
        artifact_dir: Path,
        *,
        max_audio_bytes: int,
        max_audio_seconds: float,
        max_artifacts: int,
    ) -> None:
        self.broker = broker
        self.providers = providers
        self.artifact_dir = artifact_dir
        self.max_audio_bytes = max_audio_bytes
        self.max_audio_seconds = max_audio_seconds
        self.max_artifacts = max_artifacts

    def store_audio(self, audio: bytes) -> str:
        decode_wav(audio, max_bytes=self.max_audio_bytes, max_seconds=self.max_audio_seconds, stage="tts")
        name = f"tts-{uuid4().hex}.wav"
        path = self.artifact_dir / name
        temporary = self.artifact_dir / f".{name}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as artifact:
                artifact.write(audio)
            os.replace(temporary, path)
            path.chmod(0o600)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        artifacts = sorted(
            self.artifact_dir.glob("tts-*.wav"),
            key=lambda candidate: (candidate.stat().st_mtime_ns, candidate.name),
        )
        for expired in artifacts[: -self.max_artifacts]:
            expired.unlink(missing_ok=True)
        return f"/api/v1/artifacts/{name}"

    async def _stage(self, session_id: str, name: str, operation: Callable[[], Any]) -> Any:
        await self.broker.emit(session_id, "stage.started", stage=name)
        started = perf_counter()
        try:
            result = await run_sync(operation)
        except PlatformError as exc:
            elapsed = (perf_counter() - started) * 1000
            await self.broker.emit(
                session_id,
                "stage.failed",
                stage=name,
                elapsed_ms=elapsed,
                data={"code": exc.code},
            )
            raise
        except Exception as exc:
            elapsed = (perf_counter() - started) * 1000
            await self.broker.emit(session_id, "stage.failed", stage=name, elapsed_ms=elapsed, data={"code": "stage_failed"})
            raise PlatformError(
                "stage_failed",
                f"{name} stage failed",
                status_code=500,
                stage=name,
                retryable=True,
            ) from exc
        elapsed = (perf_counter() - started) * 1000
        await self.broker.emit(session_id, "stage.completed", stage=name, elapsed_ms=elapsed)
        return result, elapsed

    async def run(self, session_id: str, audio: bytes) -> TurnResponse:
        self.broker.get(session_id)
        async with self.broker.admit_turn(session_id):
            return await self._run_admitted(session_id, audio)

    async def _run_admitted(self, session_id: str, audio: bytes) -> TurnResponse:
        await self.broker.set_state(session_id, "processing")
        await self.broker.emit(session_id, "pipeline.started")
        timings: dict[str, float] = {}
        current = "vad"
        try:
            vad, timings["vad"] = await self._stage(session_id, "vad", lambda: self.providers.vad.detect(audio))
            if not vad.get("voiced"):
                raise PlatformError("no_speech", "No speech detected", status_code=422, stage="vad", retryable=True)
            current = "asr"
            transcript, timings["asr"] = await self._stage(session_id, "asr", lambda: self.providers.asr.transcribe(audio))
            current = "correction"
            corrected, timings["correction"] = await self._stage(session_id, "correction", lambda: self.providers.correction.correct(transcript))
            current = "endpoint"
            endpoint, timings["endpoint"] = await self._stage(session_id, "endpoint", lambda: self.providers.endpoint.detect(corrected))
            current = "agent"
            response, timings["agent"] = await self._stage(session_id, "agent", lambda: self.providers.agent.respond(corrected))
            current = "tts"
            audio_url, timings["tts"] = await self._stage(
                session_id, "tts", lambda: self.store_audio(self.providers.tts.synthesize(response))
            )
        except PlatformError as exc:
            await self.broker.set_state(session_id, "failed")
            await self.broker.emit(session_id, "pipeline.failed", stage=exc.stage or current, data={"code": exc.code})
            raise
        await self.broker.set_state(session_id, "completed")
        await self.broker.emit(session_id, "pipeline.completed", data={"audio_url": audio_url})
        return TurnResponse(
            transcript=transcript,
            corrected_text=corrected,
            end_detected=endpoint[0],
            endpoint_reason=endpoint[1],
            response=response,
            audio_url=audio_url,
            latencies_ms=timings,
        )
