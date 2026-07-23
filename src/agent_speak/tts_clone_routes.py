"""Public, ephemeral TTS clone routes over the private VoxCPM2 worker."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Form, Request, Response, UploadFile

from .concurrency import run_sync
from .config import Settings
from .errors import PlatformError
from .schemas import TTSCloneStatus, TTSReferenceAssessment
from .tts_clone import ReferenceAssessment, assess_reference, compile_style_cues


class TTSCloneProvider(Protocol):
    def is_ready(self) -> bool: ...

    def synthesize(self, *, text: str, reference_wav: bytes | None) -> bytes: ...


REFERENCE_REQUEST_BODY = {
    "requestBody": {
        "description": "Validate one transient 16-bit PCM WAV voice reference without storing it.",
        "required": True,
        "content": {
            "audio/wav": {
                "schema": {
                    "type": "string",
                    "format": "binary",
                    "description": "A 5–30 second mono or stereo PCM WAV reference, up to the configured audio limit.",
                }
            }
        },
    }
}


async def _read_raw_reference(request: Request, settings: Settings) -> bytes:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "audio/wav":
        raise PlatformError(
            "unsupported_media_type",
            "Content-Type must be audio/wav",
            status_code=415,
            stage="tts_clone",
        )
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.max_audio_bytes:
                raise PlatformError(
                    "audio_too_large",
                    "Audio exceeds the configured byte limit",
                    status_code=413,
                    stage="tts_clone",
                )
        except ValueError as exc:
            raise PlatformError(
                "invalid_content_length",
                "Content-Length must be an integer",
                stage="tts_clone",
            ) from exc
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > settings.max_audio_bytes:
            raise PlatformError(
                "audio_too_large",
                "Audio exceeds the configured byte limit",
                status_code=413,
                stage="tts_clone",
            )
        body.extend(chunk)
    return bytes(body)


async def _read_upload(upload: UploadFile, settings: Settings) -> bytes:
    if upload.content_type != "audio/wav":
        raise PlatformError(
            "unsupported_media_type",
            "Voice reference Content-Type must be audio/wav",
            status_code=415,
            stage="tts_clone",
        )
    body = bytearray()
    while chunk := await upload.read(64 * 1024):
        if len(body) + len(chunk) > settings.max_audio_bytes:
            raise PlatformError(
                "audio_too_large",
                "Audio exceeds the configured byte limit",
                status_code=413,
                stage="tts_clone",
            )
        body.extend(chunk)
    return bytes(body)


def _require_runtime(settings: Settings, provider: TTSCloneProvider) -> None:
    if settings.gpu_mode != "tts":
        raise PlatformError(
            "wrong_gpu_mode",
            "TTS clone requires the exclusive TTS GPU mode",
            status_code=409,
            stage="tts_clone",
            details={"operator_hint": "./run.sh --tts-up"},
        )
    if settings.effective_accelerator != "nvidia":
        raise PlatformError(
            "gpu_unavailable",
            "TTS clone requires a supported NVIDIA GPU",
            status_code=503,
            stage="tts_clone",
            details={"operator_hint": "./run.sh --tts-up"},
        )
    if not provider.is_ready():
        raise PlatformError(
            "model_loading",
            "VoxCPM2 is not ready yet",
            status_code=503,
            stage="tts_clone",
            retryable=True,
            details={"operator_hint": "./run.sh --logs tts-worker"},
        )


def _assessment_model(result: ReferenceAssessment) -> TTSReferenceAssessment:
    return TTSReferenceAssessment(
        duration_seconds=result.duration_seconds,
        rms=result.rms,
        peak=result.peak,
        voiced_ratio=result.voiced_ratio,
        quality=result.quality,
    )


def build_tts_clone_router(
    settings: Settings,
    provider: TTSCloneProvider,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/tts-clone", tags=["TTS 克隆"])

    @router.get(
        "/status",
        response_model=TTSCloneStatus,
        summary="檢查 TTS 克隆就緒狀態",
        description="輸入：無。輸出：GPU 模式、加速器、worker 與 VoxCPM2 就緒狀態。",
    )
    async def clone_status() -> TTSCloneStatus:
        if settings.gpu_mode != "tts":
            return TTSCloneStatus(
                gpu_mode=settings.gpu_mode,
                accelerator=settings.effective_accelerator,
                state="stopped",
                device=settings.effective_accelerator,
                ready=False,
                error_code="wrong_gpu_mode",
                operator_hint="./run.sh --tts-up",
            )
        if settings.effective_accelerator != "nvidia":
            return TTSCloneStatus(
                gpu_mode=settings.gpu_mode,
                accelerator=settings.effective_accelerator,
                state="failed",
                device=settings.effective_accelerator,
                ready=False,
                error_code="gpu_unavailable",
                operator_hint="./run.sh --tts-up",
            )
        ready = await run_sync(provider.is_ready)
        return TTSCloneStatus(
            gpu_mode=settings.gpu_mode,
            accelerator=settings.effective_accelerator,
            state="ready" if ready else "loading",
            device="cuda",
            ready=ready,
            error_code=None if ready else "model_loading",
            operator_hint=None if ready else "./run.sh --logs tts-worker",
        )

    @router.post(
        "/reference/validate",
        response_model=TTSReferenceAssessment,
        openapi_extra=REFERENCE_REQUEST_BODY,
        summary="檢查克隆參考錄音",
        description="輸入：暫時性的 PCM WAV。輸出：長度、音量、人聲比例與品質；伺服器不保存音訊。",
    )
    async def validate_reference(request: Request) -> TTSReferenceAssessment:
        payload = await _read_raw_reference(request, settings)
        result = await run_sync(
            assess_reference,
            payload,
            max_bytes=settings.max_audio_bytes,
            rms_threshold=settings.vad_rms_threshold,
        )
        return _assessment_model(result)

    @router.post(
        "/synthesize",
        response_class=Response,
        responses={
            200: {
                "description": "Validated 48 kHz PCM WAV audio returned without persistence.",
                "content": {
                    "audio/wav": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                },
            }
        },
        summary="產生克隆或預設 TTS",
        description="輸入：文字、語氣提示、是否使用克隆，以及選填參考錄音。輸出：不落地保存的 48 kHz WAV。",
    )
    async def synthesize(
        text: str = Form(min_length=1, max_length=20_000),
        style_cues: list[str] = Form(default=[]),
        use_clone: bool = Form(default=False),
        reference: UploadFile | None = None,
    ) -> Response:
        await run_sync(_require_runtime, settings, provider)
        reference_wav: bytes | None = None
        if use_clone:
            if reference is None:
                raise PlatformError(
                    "reference_required",
                    "A valid voice reference is required when cloning is enabled",
                    stage="tts_clone",
                )
            reference_wav = await _read_upload(reference, settings)
            assessment = await run_sync(
                assess_reference,
                reference_wav,
                max_bytes=settings.max_audio_bytes,
                rms_threshold=settings.vad_rms_threshold,
            )
            if assessment.quality != "good":
                raise PlatformError(
                    "invalid_reference",
                    "Voice reference does not meet the quality requirements",
                    stage="tts_clone",
                    details={"quality": assessment.quality},
                )
        compiled = compile_style_cues(style_cues, text)
        audio = await run_sync(
            provider.synthesize,
            text=compiled,
            reference_wav=reference_wav,
        )
        return Response(
            content=audio,
            media_type="audio/wav",
            headers={
                "X-Agent-Speak-Model": "voxcpm2",
                "Cache-Control": "no-store",
            },
        )

    return router
