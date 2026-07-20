"""Internal-only FastAPI service owning the Faster-Whisper model."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .audio import decode_wav
from .concurrency import run_sync
from .config import Settings
from .errors import PlatformError
from .production import FasterWhisperASR


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


def create_asr_worker(
    *,
    provider: Any | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    active = settings or Settings.from_env()
    asr = provider or FasterWhisperASR(
        model_name=active.asr_model,
        language=active.asr_language,
        accelerator=active.accelerator,
        cpu_compute_type=active.asr_compute_type,
        cuda_compute_type=active.asr_cuda_compute_type,
        cpu_threads=active.asr_cpu_threads,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            await run_sync(asr.warm)
            app.state.ready = True
            app.state.warm_error = None
        except Exception as exc:
            app.state.ready = False
            app.state.warm_error = exc
        yield

    app = FastAPI(
        title="Agent Speak ASR Worker",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.ready = False
    app.state.warm_error = None
    app.state.provider = asr

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
        return JSONResponse(
            status_code=200 if app.state.ready else 503,
            content={
                "ready": app.state.ready,
                "device": asr.device,
            },
        )

    @app.post("/internal/v1/asr")
    async def transcribe(
        request: Request,
        mode: Literal["partial", "final"] = "final",
    ) -> dict[str, str]:
        if not app.state.ready:
            raise PlatformError(
                "provider_unavailable",
                "ASR worker is not ready",
                status_code=503,
                stage="asr",
                retryable=True,
            )
        audio = await _read_wav(request, active)
        text = await run_sync(asr.transcribe, audio)
        return {"text": text, "device": asr.device, "mode": mode}

    return app


app = create_asr_worker()
