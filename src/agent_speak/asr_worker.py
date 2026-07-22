"""Internal-only FastAPI service owning one selectable ASR model."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .asr_model_manager import ASRModelManager, ModelLeaseConflict
from .asr_providers import BreezeASR, Qwen3ASR
from .audio import decode_wav
from .concurrency import run_sync
from .config import Settings
from .errors import PlatformError
from .model_ids import ASRModelId, DEFAULT_ASR_MODEL
from .production import FasterWhisperASR
from .speech_languages import SpeechLanguage, whisper_language


async def _read_wav(request: Request, settings: Settings) -> bytes:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "audio/wav":
        raise PlatformError(
            "unsupported_media_type",
            "Content-Type must be audio/wav",
            status_code=415,
            stage="asr",
        )
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > settings.max_audio_bytes:
            raise PlatformError(
                "audio_too_large",
                "Audio exceeds the configured byte limit",
                status_code=413,
                stage="asr",
            )
        body.extend(chunk)
    audio = bytes(body)
    decode_wav(
        audio,
        max_bytes=settings.max_audio_bytes,
        max_seconds=settings.max_audio_seconds,
        stage="asr",
    )
    return audio


class ModelActivationRequest(BaseModel):
    asr_model: ASRModelId


def _configured_manager(settings: Settings) -> ASRModelManager:
    model_root = settings.models_root
    factories = {
        "faster-whisper-small": lambda: FasterWhisperASR(
            model_name=str(model_root / "asr" / "faster-whisper-small"),
            language=settings.asr_language,
            accelerator=settings.accelerator,
            cpu_compute_type=settings.asr_compute_type,
            cuda_compute_type=settings.asr_cuda_compute_type,
            cpu_threads=settings.asr_cpu_threads,
        ),
        "breeze-asr-25": lambda: BreezeASR(
            model_path=model_root / "asr" / "breeze-asr-25",
            accelerator=settings.accelerator,
            max_audio_bytes=settings.max_audio_bytes,
            max_audio_seconds=settings.max_audio_seconds,
        ),
        "qwen3-asr-1.7b": lambda: Qwen3ASR(
            model_path=model_root / "asr" / "qwen3-asr-1.7b",
            accelerator=settings.accelerator,
            max_audio_bytes=settings.max_audio_bytes,
            max_audio_seconds=settings.max_audio_seconds,
        ),
    }
    return ASRModelManager(factories=factories, device=settings.effective_accelerator)


def create_asr_worker(
    *,
    provider: Any | None = None,
    manager: ASRModelManager | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    active = settings or Settings.from_env()
    if provider is not None and manager is not None:
        raise ValueError("provider and manager are mutually exclusive")
    if manager is not None:
        model_manager = manager
        initial_model: ASRModelId = DEFAULT_ASR_MODEL
    elif provider is not None:
        model_manager = ASRModelManager(
            factories={"faster-whisper-small": lambda: provider},
            device=provider.device,
            memory_cleanup=lambda: None,
        )
        initial_model = "faster-whisper-small"
    else:
        model_manager = _configured_manager(active)
        initial_model = DEFAULT_ASR_MODEL

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            await run_sync(model_manager.activate, initial_model)
            app.state.activation_error = None
        except PlatformError as exc:
            app.state.activation_error = exc
        yield
        activation_task: asyncio.Task[None] | None = app.state.activation_task
        if activation_task is not None and not activation_task.done():
            await activation_task

    app = FastAPI(
        title="Agent Speak ASR Worker",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.manager = model_manager
    app.state.activation_task = None
    app.state.activation_error = None

    @app.exception_handler(PlatformError)
    async def platform_error(_: Request, exc: PlatformError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "stage": exc.stage,
                    "retryable": exc.retryable,
                }
            },
        )

    @app.get("/internal/v1/health")
    async def health() -> JSONResponse:
        snapshot = model_manager.snapshot()
        ready = snapshot.state == "ready" and snapshot.active_asr_model is not None
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "ready": ready,
                "device": snapshot.device,
                "model": asdict(snapshot),
            },
        )

    @app.get("/internal/v1/models")
    async def models() -> dict[str, object]:
        return asdict(model_manager.snapshot())

    async def activate_in_background(model_id: ASRModelId) -> None:
        try:
            await run_sync(model_manager.activate, model_id)
            app.state.activation_error = None
        except PlatformError as exc:
            app.state.activation_error = exc

    @app.put("/internal/v1/models/active")
    async def activate_model(request: ModelActivationRequest) -> JSONResponse:
        snapshot = model_manager.snapshot()
        if snapshot.leased_by is not None and request.asr_model != snapshot.active_asr_model:
            raise ModelLeaseConflict()
        if snapshot.state == "ready" and snapshot.active_asr_model == request.asr_model:
            return JSONResponse(status_code=200, content=asdict(snapshot))
        task: asyncio.Task[None] | None = app.state.activation_task
        if task is not None and not task.done():
            if snapshot.requested_asr_model != request.asr_model:
                raise PlatformError(
                    "model_activation_in_progress",
                    "Another ASR model activation is already in progress",
                    status_code=409,
                    stage="asr",
                    retryable=True,
                )
            return JSONResponse(status_code=202, content=asdict(snapshot))
        app.state.activation_task = asyncio.create_task(activate_in_background(request.asr_model))
        return JSONResponse(status_code=202, content=asdict(model_manager.snapshot()))

    @app.post("/internal/v1/models/lease/{session_id}")
    async def acquire_model_lease(session_id: str, asr_model: ASRModelId) -> dict[str, object]:
        return asdict(await run_sync(model_manager.acquire, session_id, asr_model))

    @app.delete("/internal/v1/models/lease/{session_id}")
    async def release_model_lease(session_id: str) -> dict[str, object]:
        return asdict(await run_sync(model_manager.release, session_id))

    @app.post("/internal/v1/asr")
    async def transcribe(
        request: Request,
        mode: Literal["partial", "final"] = "final",
        speech_language: SpeechLanguage | None = None,
        asr_model: ASRModelId | None = None,
        session_id: str | None = None,
    ) -> dict[str, str]:
        snapshot = model_manager.snapshot()
        selected_model = asr_model or snapshot.active_asr_model
        if snapshot.state != "ready" or selected_model is None:
            raise PlatformError(
                "provider_unavailable",
                "ASR worker is not ready",
                status_code=503,
                stage="asr",
                retryable=True,
            )
        audio = await _read_wav(request, active)
        language = active.asr_language if speech_language is None else whisper_language(speech_language)
        text = await run_sync(
            model_manager.transcribe,
            session_id,
            selected_model,
            audio,
            language=language,
        )
        return {
            "text": text,
            "device": model_manager.snapshot().device,
            "mode": mode,
            "asr_model": selected_model,
        }

    return app


app = create_asr_worker()
