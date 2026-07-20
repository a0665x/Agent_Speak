"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from . import __version__
from .audio import EnergyVAD, decode_wav
from .concurrency import run_sync
from .config import Settings
from .errors import PlatformError
from .pipeline import Pipeline, ProviderSet
from .schemas import (
    CapabilitiesResponse,
    EndDetectOutput,
    ErrorBody,
    ErrorEnvelope,
    HealthResponse,
    SessionSummary,
    SpeakerCreate,
    SpeakerEnvelope,
    SpeakerList,
    SpeakerMatchEnvelope,
    SpeakerUpdate,
    TextInput,
    TextOutput,
    TtsOutput,
    TurnResponse,
    VadOutput,
)
from .sessions import SessionBroker
from .speakers import SPEAKER_NOTICE, SpeakerStore


SECURITY_HEADERS = (
    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
)
DOCS_SECURITY_HEADERS = (
    (
        b"content-security-policy",
        b"default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://cdn.jsdelivr.net; connect-src 'self'; img-src 'self' data: https://fastapi.tiangolo.com; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
    ),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
)
WAV_REQUEST_BODY = {
    "requestBody": {
        "description": "上傳單一 PCM WAV 音訊檔。Content-Type 必須是 audio/wav；大小最多 8 MiB、長度最多 30 秒（實際限制可由服務設定調整）。",
        "required": True,
        "content": {
            "audio/wav": {
                "schema": {
                    "type": "string",
                    "format": "binary",
                    "description": "16-bit PCM WAV 二進位內容；建議單聲道。上限 8 MiB、30 秒。",
                }
            }
        },
    }
}


OPENAPI_TAGS = [
    {"name": "系統", "description": "確認服務健康狀態與目前實際啟用的處理能力。"},
    {"name": "對話流程", "description": "建立工作階段並一次執行完整語音對話流程。"},
    {"name": "語音階段", "description": "單獨測試 VAD 與 ASR 語音處理階段。"},
    {"name": "文字階段", "description": "單獨測試文字校正、結束判斷、Agent 與 TTS。"},
    {"name": "說話者", "description": "管理本機便利識別資料；不是生物辨識身分驗證。"},
    {"name": "音訊成品", "description": "讀取 TTS 產生的本機 WAV 音訊。"},
]


class SecurityHeadersMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        headers = DOCS_SECURITY_HEADERS if scope.get("path") in {"/docs", "/redoc"} else SECURITY_HEADERS

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *headers]
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _error_response(status: int, body: ErrorBody) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorEnvelope(error=body).model_dump(mode="json"))


async def _invoke_stage(stage: str, operation: Callable[[], Any]) -> Any:
    try:
        return await run_sync(operation)
    except PlatformError:
        raise
    except Exception as exc:
        raise PlatformError(
            "stage_failed",
            f"{stage} stage failed",
            status_code=500,
            stage=stage,
            retryable=True,
        ) from exc


async def _read_audio(request: Request, settings: Settings, *, stage: str) -> bytes:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "audio/wav":
        raise PlatformError(
            "unsupported_media_type", "Content-Type must be audio/wav", status_code=415, stage=stage
        )
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.max_audio_bytes:
                raise PlatformError(
                    "audio_too_large", "Audio exceeds the configured byte limit", status_code=413, stage=stage
                )
        except ValueError as exc:
            raise PlatformError("invalid_content_length", "Content-Length must be an integer", stage=stage) from exc
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > settings.max_audio_bytes:
            raise PlatformError(
                "audio_too_large", "Audio exceeds the configured byte limit", status_code=413, stage=stage
            )
        body.extend(chunk)
    audio = bytes(body)
    decode_wav(audio, max_bytes=settings.max_audio_bytes, max_seconds=settings.max_audio_seconds, stage=stage)
    return audio


def create_app(settings: Settings | None = None, *, providers: ProviderSet | None = None) -> FastAPI:
    active = settings or Settings.from_env()
    active.prepare_directories()
    app = FastAPI(
        title="Agent Speak",
        version=__version__,
        description=(
            "Agent Speak 是本機語音處理 API。新手可先建立工作階段，再把 PCM WAV 上傳至完整對話端點；"
            "也可依序呼叫各階段端點。所有錯誤都使用一致的 error envelope。"
        ),
        openapi_tags=OPENAPI_TAGS,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.state.settings = active
    app.state.broker = SessionBroker(
        max_sessions=active.max_sessions,
        max_events=active.max_session_events,
        subscriber_queue_size=active.max_event_queue,
    )
    default_vad = EnergyVAD(
        max_bytes=active.max_audio_bytes,
        max_seconds=active.max_audio_seconds,
        rms_threshold=active.vad_rms_threshold,
    )
    app.state.pipeline = Pipeline(
        app.state.broker,
        providers or ProviderSet.configured(active, vad=default_vad),
        active.runtime_dir / "artifacts",
        max_audio_bytes=active.max_audio_bytes,
        max_audio_seconds=active.max_audio_seconds,
        max_artifacts=active.max_artifacts,
    )
    app.state.speakers = SpeakerStore(
        active.data_dir / "speakers.sqlite3",
        active.data_dir / "speaker_samples",
        max_audio_bytes=active.max_audio_bytes,
        max_audio_seconds=active.max_audio_seconds,
    )
    web_dir = Path(__file__).resolve().parents[2] / "web"

    @app.exception_handler(PlatformError)
    async def platform_error(_: Request, exc: PlatformError) -> JSONResponse:
        return _error_response(
            exc.status_code,
            ErrorBody(code=exc.code, message=exc.message, stage=exc.stage, retryable=exc.retryable, details=exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            422,
            ErrorBody(code="validation_error", message="Request validation failed", details={"errors": exc.errors()}),
        )

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return _error_response(exc.status_code, ErrorBody(code=code, message=str(exc.detail)))

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, __: Exception) -> JSONResponse:
        return _error_response(500, ErrorBody(code="internal_error", message="Internal server error"))

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["系統"], summary="檢查服務健康狀態", description="輸入：可選 verbose 查詢參數。輸出：版本、狀態與本機儲存是否就緒。")
    async def health(verbose: bool = Query(default=False)) -> HealthResponse:
        del verbose
        return HealthResponse(version=__version__, storage_ready=active.data_dir.is_dir())

    @app.get("/api/v1/capabilities", response_model=CapabilitiesResponse, tags=["系統"], summary="查看目前處理能力", description="輸入：無。輸出：六個處理階段實際啟用的提供者、版本與限制。")
    async def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(providers=app.state.pipeline.providers.capabilities())

    @app.get("/", include_in_schema=False)
    async def web_console() -> Response:
        return Response(content=(web_dir / "index.html").read_text(encoding="utf-8"), media_type="text/html")

    @app.get("/app.css", include_in_schema=False)
    @app.get("/static/app.css", include_in_schema=False)
    async def web_styles() -> Response:
        return Response(content=(web_dir / "app.css").read_text(encoding="utf-8"), media_type="text/css")

    @app.get("/app.js", include_in_schema=False)
    @app.get("/static/app.js", include_in_schema=False)
    async def web_script() -> Response:
        return Response(content=(web_dir / "app.js").read_text(encoding="utf-8"), media_type="text/javascript")

    @app.get("/codex", include_in_schema=False)
    async def codex_recorder() -> Response:
        return Response(content=(web_dir / "codex.html").read_text(encoding="utf-8"), media_type="text/html")

    @app.get("/static/codex.css", include_in_schema=False)
    async def codex_styles() -> Response:
        return Response(content=(web_dir / "codex.css").read_text(encoding="utf-8"), media_type="text/css")

    @app.get("/static/codex-recorder-core.js", include_in_schema=False)
    async def codex_recorder_core() -> Response:
        return Response(
            content=(web_dir / "codex-recorder-core.js").read_text(encoding="utf-8"), media_type="text/javascript"
        )

    @app.get("/static/codex.js", include_in_schema=False)
    async def codex_script() -> Response:
        return Response(content=(web_dir / "codex.js").read_text(encoding="utf-8"), media_type="text/javascript")

    @app.post("/api/v1/sessions", response_model=SessionSummary, status_code=status.HTTP_201_CREATED, tags=["對話流程"], summary="建立對話工作階段", description="輸入：無。輸出：新的工作階段識別碼、狀態與事件清單。")
    async def create_session() -> SessionSummary:
        return await app.state.broker.create()

    @app.get("/api/v1/sessions/{session_id}", response_model=SessionSummary, tags=["對話流程"], summary="取得對話工作階段", description="輸入：工作階段識別碼。輸出：目前狀態與已保留的流程事件。")
    async def get_session(session_id: str) -> SessionSummary:
        return app.state.broker.get(session_id)

    @app.websocket("/api/v1/sessions/{session_id}/events")
    async def session_events(websocket: WebSocket, session_id: str) -> None:
        try:
            app.state.broker.get(session_id)
        except PlatformError:
            await websocket.close(code=4404, reason="Session not found")
            return
        await websocket.accept()
        try:
            async for event in app.state.broker.subscribe(session_id):
                await websocket.send_json(event.model_dump(mode="json"))
        except WebSocketDisconnect:
            return

    @app.post(
        "/api/v1/sessions/{session_id}/turns", response_model=TurnResponse, openapi_extra=WAV_REQUEST_BODY,
        tags=["對話流程"], summary="執行完整語音回合", description="輸入：PCM WAV 與工作階段識別碼。輸出：辨識、校正、Agent 回覆、WAV 網址與各階段耗時。"
    )
    async def full_turn(request: Request, session_id: str) -> TurnResponse:
        app.state.broker.get(session_id)
        audio = await _read_audio(request, active, stage="vad")
        return await app.state.pipeline.run(session_id, audio)

    @app.post("/api/v1/audio/vad", response_model=VadOutput, openapi_extra=WAV_REQUEST_BODY, tags=["語音階段"], summary="偵測音訊中的人聲", description="輸入：PCM WAV 音訊。輸出：是否有人聲、RMS 能量與音訊秒數。")
    async def vad(request: Request) -> VadOutput:
        audio = await _read_audio(request, active, stage="vad")
        return VadOutput.model_validate(await _invoke_stage("vad", lambda: app.state.pipeline.providers.vad.detect(audio)))

    @app.post("/api/v1/audio/asr", response_model=TextOutput, openapi_extra=WAV_REQUEST_BODY, tags=["語音階段"], summary="將語音辨識為文字", description="輸入：PCM WAV 音訊。輸出：ASR 辨識文字。")
    async def asr(request: Request) -> TextOutput:
        audio = await _read_audio(request, active, stage="asr")
        return TextOutput(text=await _invoke_stage("asr", lambda: app.state.pipeline.providers.asr.transcribe(audio)))

    @app.post("/api/v1/text/correct", response_model=TextOutput, tags=["文字階段"], summary="校正辨識文字", description="輸入：要清理的辨識文字。輸出：校正後、較易閱讀的文字。")
    async def correct(body: TextInput) -> TextOutput:
        return TextOutput(text=await _invoke_stage("correction", lambda: app.state.pipeline.providers.correction.correct(body.text)))

    @app.post("/api/v1/text/end-detect", response_model=EndDetectOutput, tags=["文字階段"], summary="判斷語句是否結束", description="輸入：校正後文字。輸出：是否已完成語句及判定原因。")
    async def end_detect(body: TextInput) -> EndDetectOutput:
        complete, reason = await _invoke_stage("endpoint", lambda: app.state.pipeline.providers.endpoint.detect(body.text))
        return EndDetectOutput(complete=complete, reason=reason)

    @app.post("/api/v1/agent/respond", response_model=TextOutput, tags=["文字階段"], summary="產生 Agent 回覆", description="輸入：使用者文字。輸出：目前 Agent 提供者產生的文字回覆。")
    async def respond(body: TextInput) -> TextOutput:
        return TextOutput(text=await _invoke_stage("agent", lambda: app.state.pipeline.providers.agent.respond(body.text)))

    @app.post("/api/v1/tts/synthesize", response_model=TtsOutput, tags=["文字階段"], summary="將文字合成語音", description="輸入：要朗讀的文字。輸出：可下載或播放的 WAV 站內網址。")
    async def synthesize(body: TextInput) -> TtsOutput:
        audio_url = await _invoke_stage(
            "tts", lambda: app.state.pipeline.store_audio(app.state.pipeline.providers.tts.synthesize(body.text))
        )
        return TtsOutput(audio_url=audio_url)

    @app.get(
        "/api/v1/artifacts/{name}",
        response_class=Response,
        responses={
            200: {
                "description": "有效的 16-bit PCM WAV 音訊",
                "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
            }
        },
        tags=["音訊成品"],
        summary="取得合成 WAV 音訊",
        description="輸入：TTS 回傳的 WAV 檔名。輸出：audio/wav 二進位音訊。",
    )
    async def artifact(name: str) -> Response:
        if "/" in name or "\\" in name or not name.endswith(".wav"):
            raise PlatformError("artifact_not_found", "Artifact not found", status_code=404)
        path = active.runtime_dir / "artifacts" / name
        if not path.is_file():
            raise PlatformError("artifact_not_found", "Artifact not found", status_code=404)
        def read_validated_artifact() -> bytes:
            payload = path.read_bytes()
            decode_wav(
                payload,
                max_bytes=active.max_audio_bytes,
                max_seconds=active.max_audio_seconds,
                stage="tts",
            )
            return payload

        payload = await run_sync(read_validated_artifact)
        return Response(
            content=payload,
            media_type="audio/wav",
            headers={"Content-Disposition": f'inline; filename="{name}"'},
        )

    @app.post("/api/v1/speakers", response_model=SpeakerEnvelope, status_code=status.HTTP_201_CREATED, tags=["說話者"], summary="建立說話者資料", description="輸入：名稱與選填備註。輸出：新建的本機說話者資料；此功能不是身分驗證。")
    async def create_speaker(body: SpeakerCreate) -> SpeakerEnvelope:
        speaker = await run_sync(app.state.speakers.create, body.name, body.notes)
        return SpeakerEnvelope(speaker=speaker, notice=SPEAKER_NOTICE)

    @app.get("/api/v1/speakers", response_model=SpeakerList, tags=["說話者"], summary="列出說話者資料", description="輸入：無。輸出：所有本機說話者資料與安全提醒。")
    async def list_speakers() -> SpeakerList:
        return SpeakerList(speakers=await run_sync(app.state.speakers.list), notice=SPEAKER_NOTICE)

    @app.get("/api/v1/speakers/{speaker_id}", response_model=SpeakerEnvelope, tags=["說話者"], summary="取得說話者資料", description="輸入：說話者識別碼。輸出：指定的本機資料與樣本數。")
    async def get_speaker(speaker_id: str) -> SpeakerEnvelope:
        return SpeakerEnvelope(speaker=await run_sync(app.state.speakers.get, speaker_id), notice=SPEAKER_NOTICE)

    @app.patch("/api/v1/speakers/{speaker_id}", response_model=SpeakerEnvelope, tags=["說話者"], summary="更新說話者資料", description="輸入：說話者識別碼、完整名稱與備註。輸出：更新後的資料。")
    async def update_speaker(speaker_id: str, body: SpeakerUpdate) -> SpeakerEnvelope:
        speaker = await run_sync(app.state.speakers.update, speaker_id, body.name, body.notes)
        return SpeakerEnvelope(speaker=speaker, notice=SPEAKER_NOTICE)

    @app.delete("/api/v1/speakers/{speaker_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["說話者"], summary="刪除說話者資料", description="輸入：說話者識別碼。輸出：成功時為 204，並刪除其本機樣本。")
    async def delete_speaker(speaker_id: str) -> Response:
        await run_sync(app.state.speakers.delete, speaker_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/v1/speakers/{speaker_id}/samples", response_model=SpeakerEnvelope, openapi_extra=WAV_REQUEST_BODY,
        tags=["說話者"], summary="登錄說話者語音樣本", description="輸入：說話者識別碼與 PCM WAV。輸出：樣本數已更新的資料；只供便利識別。"
    )
    async def enroll_speaker(request: Request, speaker_id: str) -> SpeakerEnvelope:
        audio = await _read_audio(request, active, stage="speaker")
        speaker = await run_sync(app.state.speakers.enroll, speaker_id, audio)
        return SpeakerEnvelope(speaker=speaker, notice=SPEAKER_NOTICE)

    @app.post("/api/v1/speakers/match", response_model=SpeakerMatchEnvelope, openapi_extra=WAV_REQUEST_BODY, tags=["說話者"], summary="比對說話者語音", description="輸入：PCM WAV。輸出：最接近且達門檻的本機資料、分數與門檻；不是身分驗證。")
    async def match_speaker(request: Request) -> SpeakerMatchEnvelope:
        audio = await _read_audio(request, active, stage="speaker")
        result = await run_sync(app.state.speakers.match, audio)
        return SpeakerMatchEnvelope(**result.model_dump(), notice=SPEAKER_NOTICE)

    return app


app = create_app()
