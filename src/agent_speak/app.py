"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from . import __version__
from .audio import EnergyVAD, decode_wav
from .concurrency import run_sync
from .config import Settings
from .errors import PlatformError
from .locales import DOCS_UI_TEXT, localize_openapi, normalize_locale
from .model_ids import (
    ASRModelId,
    CorrectionModelId,
    DEFAULT_ASR_MODEL,
    DEFAULT_CORRECTION_MODEL,
)
from .model_control import ASRWorkerControlClient, ModelCatalogService, UnavailableWorkerModelControl
from .pipeline import Pipeline, ProviderSet
from .realtime import RealtimeCoordinator, RealtimeTextAdapter
from .realtime_audio import EnergyFrameVAD
from .realtime_routes import register_realtime_routes
from .schemas import (
    CapabilitiesResponse,
    EndDetectOutput,
    ErrorBody,
    ErrorEnvelope,
    HealthResponse,
    ModelActivationInput,
    ModelCatalog,
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
from .speech_languages import DEFAULT_SPEECH_LANGUAGE, SpeechLanguage
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


def create_app(
    settings: Settings | None = None,
    *,
    providers: ProviderSet | None = None,
    realtime: RealtimeCoordinator | None = None,
    model_control: ModelCatalogService | None = None,
) -> FastAPI:
    active = settings or Settings.from_env()
    active.prepare_directories()
    app = FastAPI(
        title="Agent Speak",
        version=__version__,
        docs_url=None,
        description=(
            "Agent Speak 是本機語音處理 API。新手可先建立工作階段，再把 PCM WAV 上傳至完整對話端點；"
            "也可依序呼叫各階段端點。所有錯誤都使用一致的 error envelope。"
        ),
        openapi_tags=OPENAPI_TAGS,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.state.settings = active
    app.state.localized_openapi = {}
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
    worker_control = (
        ASRWorkerControlClient(active.asr_worker_url)
        if active.asr_worker_url
        else UnavailableWorkerModelControl()
    )
    app.state.model_control = model_control or ModelCatalogService(
        worker=worker_control,
        correction_ready=lambda: next(
            item.ready
            for item in app.state.pipeline.providers.capabilities()
            if item.stage == "correction"
        ),
    )
    app.state.realtime = realtime or RealtimeCoordinator(
        active,
        vad=EnergyFrameVAD(threshold=active.vad_rms_threshold),
        asr=app.state.pipeline.providers.asr,
        text=RealtimeTextAdapter(
            app.state.pipeline.providers.endpoint,
            app.state.pipeline.providers.correction,
        ),
        broker=app.state.broker,
        model_control=app.state.model_control,
    )
    if app.state.realtime.broker is None:
        app.state.realtime.broker = app.state.broker
    register_realtime_routes(app)
    app.state.speakers = SpeakerStore(
        active.data_dir / "speakers.sqlite3",
        active.data_dir / "speaker_samples",
        max_audio_bytes=active.max_audio_bytes,
        max_audio_seconds=active.max_audio_seconds,
    )
    web_dir = Path(__file__).resolve().parents[2] / "web"
    asr_realtime_web_dir = web_dir / "asr_realtime"
    asr_realtime_assets = asr_realtime_web_dir / "assets"
    if asr_realtime_assets.is_dir():
        app.mount(
            "/asr_realtime/assets",
            StaticFiles(directory=asr_realtime_assets),
            name="asr-realtime-assets",
        )

    @app.middleware("http")
    async def localized_openapi_document(request: Request, call_next: Callable[[Request], Any]) -> Response:
        if request.url.path != "/openapi.json":
            return await call_next(request)
        locale = normalize_locale(request.query_params.get("lang"))
        cached = app.state.localized_openapi.get(locale)
        if cached is None:
            cached = localize_openapi(app.openapi(), locale)
            app.state.localized_openapi[locale] = cached
        return JSONResponse(cached)

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

    @app.get(
        "/api/v1/models",
        response_model=ModelCatalog,
        tags=["系統"],
        summary="查看可用推論模型",
        description="輸入：無。輸出：ASR、校正選項，以及目前載入與租用狀態。",
    )
    async def models() -> ModelCatalog:
        return await run_sync(app.state.model_control.catalog)

    @app.put(
        "/api/v1/models/active",
        response_model=ModelCatalog,
        tags=["系統"],
        summary="切換啟用的推論模型",
        description="輸入：ASR 模型與校正策略。輸出：切換後或載入中的完整模型狀態。",
    )
    async def activate_models(body: ModelActivationInput) -> ModelCatalog:
        return await run_sync(
            app.state.model_control.activate,
            body.asr_model,
            body.correction_model,
        )

    @app.get("/docs", include_in_schema=False)
    async def localized_docs(lang: str | None = None) -> Response:
        locale = normalize_locale(lang)
        copy = DOCS_UI_TEXT[locale]
        options = "".join(
            f'<option value="{value}"{" selected" if value == locale else ""}>{label}</option>'
            for value, label in (
                ("en", "English"),
                ("zh-TW", "繁體中文"),
                ("ja", "日本語"),
                ("ko", "한국어"),
            )
        )
        page = f"""<!doctype html>
<html lang="{locale}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{copy['title']}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
  <link rel="stylesheet" href="/static/docs-locale.css">
  <script src="/static/docs-locale.js" defer></script>
</head>
<body data-current-locale="{locale}">
  <header class="docs-nav">
    <a href="/?lang={locale}" aria-label="{copy['home']}"><span aria-hidden="true"></span>Agent Speak</a>
    <label for="language-select">{copy['language']}</label>
    <select id="language-select" aria-label="{copy['language']}" data-current-locale="{locale}">{options}</select>
  </header>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({{
      url: "/openapi.json?lang={locale}",
      dom_id: "#swagger-ui",
      deepLinking: true,
      showExtensions: true,
      showCommonExtensions: true,
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset]
    }});
  </script>
</body>
</html>"""
        return Response(content=page, media_type="text/html")

    @app.get("/", include_in_schema=False)
    async def web_console() -> Response:
        return Response(content=(web_dir / "index.html").read_text(encoding="utf-8"), media_type="text/html")

    @app.get("/asr_realtime", include_in_schema=False)
    @app.get("/asr_realtime/", include_in_schema=False)
    async def asr_realtime_studio() -> Response:
        index = asr_realtime_web_dir / "index.html"
        if not index.is_file():
            raise PlatformError(
                "realtime_ui_unavailable",
                "Realtime Studio has not been built",
                status_code=503,
            )
        return Response(content=index.read_text(encoding="utf-8"), media_type="text/html")

    @app.get("/asr_realtime/pcm-capture.worklet.js", include_in_schema=False)
    async def asr_realtime_audio_worklet() -> Response:
        return Response(
            content=(asr_realtime_web_dir / "pcm-capture.worklet.js").read_text(encoding="utf-8"),
            media_type="text/javascript",
        )

    @app.get("/realtime", include_in_schema=False)
    async def legacy_realtime_studio() -> RedirectResponse:
        return RedirectResponse("/asr_realtime", status_code=307)

    @app.get("/realtime/", include_in_schema=False)
    async def legacy_realtime_studio_slash() -> RedirectResponse:
        return RedirectResponse("/asr_realtime/", status_code=307)

    @app.get("/realtime/pcm-capture.worklet.js", include_in_schema=False)
    async def legacy_realtime_audio_worklet() -> RedirectResponse:
        return RedirectResponse("/asr_realtime/pcm-capture.worklet.js", status_code=307)

    @app.get("/app.css", include_in_schema=False)
    @app.get("/static/app.css", include_in_schema=False)
    async def web_styles() -> Response:
        return Response(content=(web_dir / "app.css").read_text(encoding="utf-8"), media_type="text/css")

    @app.get("/static/docs-locale.css", include_in_schema=False)
    async def docs_locale_styles() -> Response:
        return Response(content=(web_dir / "docs-locale.css").read_text(encoding="utf-8"), media_type="text/css")

    @app.get("/app.js", include_in_schema=False)
    @app.get("/static/app.js", include_in_schema=False)
    async def web_script() -> Response:
        return Response(content=(web_dir / "app.js").read_text(encoding="utf-8"), media_type="text/javascript")

    @app.get("/static/locale.js", include_in_schema=False)
    async def web_locale_script() -> Response:
        return Response(content=(web_dir / "locale.js").read_text(encoding="utf-8"), media_type="text/javascript")

    @app.get("/static/docs-locale.js", include_in_schema=False)
    async def docs_locale_script() -> Response:
        return Response(content=(web_dir / "docs-locale.js").read_text(encoding="utf-8"), media_type="text/javascript")

    @app.get("/static/speech-core-hero.png", include_in_schema=False)
    async def speech_core_artwork() -> Response:
        return Response(content=(web_dir / "speech-core-hero.png").read_bytes(), media_type="image/png")

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
    async def create_session(
        speech_language: SpeechLanguage = DEFAULT_SPEECH_LANGUAGE,
        asr_model: ASRModelId = DEFAULT_ASR_MODEL,
        correction_model: CorrectionModelId = DEFAULT_CORRECTION_MODEL,
    ) -> SessionSummary:
        return await app.state.broker.create(
            speech_language=speech_language,
            asr_model=asr_model,
            correction_model=correction_model,
        )

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
