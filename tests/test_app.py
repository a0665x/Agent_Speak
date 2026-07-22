from pathlib import Path

import httpx
import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings
from agent_speak.errors import PlatformError
from agent_speak.model_control import ModelCatalogService


def make_client(tmp_path: Path) -> httpx.AsyncClient:
    settings = Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime")
    app = create_app(settings)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


class FakeWorkerModelControl:
    def __init__(self) -> None:
        self.active = "qwen3-asr-1.7b"
        self.correction = "qwen2.5-correction"
        self.leased_by: str | None = None

    def snapshot(self) -> dict[str, object]:
        return {
            "state": "ready",
            "active_asr_model": self.active,
            "requested_asr_model": None,
            "leased_by": self.leased_by,
            "device": "cuda",
            "error_code": None,
        }

    def activate(self, model_id: str) -> dict[str, object]:
        if self.leased_by is not None and model_id != self.active:
            raise PlatformError(
                "model_in_use",
                "The active ASR model is in use by another session",
                status_code=409,
                stage="asr",
                retryable=True,
            )
        self.active = model_id
        return self.snapshot()

    def acquire(self, session_id: str, model_id: str) -> dict[str, object]:
        del model_id
        self.leased_by = session_id
        return self.snapshot()

    def release(self, session_id: str) -> dict[str, object]:
        if self.leased_by == session_id:
            self.leased_by = None
        return self.snapshot()


def app_with_model_control(tmp_path: Path) -> tuple[object, FakeWorkerModelControl]:
    worker = FakeWorkerModelControl()
    control = ModelCatalogService(worker=worker, correction_ready=lambda: True)
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
        model_control=control,
    )
    return app, worker


@pytest.mark.anyio
async def test_public_model_catalog_and_direct_activation(tmp_path: Path) -> None:
    app, _ = app_with_model_control(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        before = await client.get("/api/v1/models")
        changed = await client.put(
            "/api/v1/models/active",
            json={"asr_model": "breeze-asr-25", "correction_model": "disabled"},
        )

    assert before.status_code == 200
    assert {item["id"] for item in before.json()["asr"]} == {
        "faster-whisper-small",
        "breeze-asr-25",
        "qwen3-asr-1.7b",
    }
    assert changed.status_code in {200, 202}
    assert changed.json()["active"]["asr_model"] == "breeze-asr-25"
    assert changed.json()["active"]["correction_model"] == "disabled"


@pytest.mark.anyio
async def test_public_model_activation_rejects_unknown_ids_and_active_lease(tmp_path: Path) -> None:
    app, worker = app_with_model_control(tmp_path)
    worker.leased_by = "session-a"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        unknown = await client.put(
            "/api/v1/models/active",
            json={"asr_model": "unknown", "correction_model": "disabled"},
        )
        conflict = await client.put(
            "/api/v1/models/active",
            json={"asr_model": "breeze-asr-25", "correction_model": "disabled"},
        )

    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "validation_error"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "model_in_use"


@pytest.mark.anyio
async def test_health_and_capabilities_expose_runtime_truth(tmp_path: Path) -> None:
    async with make_client(tmp_path) as client:
        health = await client.get("/api/v1/health")
        capabilities = await client.get("/api/v1/capabilities")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["version"] == "0.1.1"
    providers = {item["stage"]: item for item in capabilities.json()["providers"]}
    assert set(providers) == {"vad", "asr", "correction", "endpoint", "agent", "tts"}
    assert providers["vad"]["development"] is False
    assert providers["asr"]["development"] is False
    assert providers["tts"]["development"] is False
    assert providers["asr"]["name"] == "faster-whisper-small"
    assert providers["tts"]["name"] == "piper-zh_CN-huayan-medium"
    assert all(providers[name]["development"] for name in ("correction", "endpoint", "agent"))


@pytest.mark.anyio
async def test_responses_include_browser_security_headers(tmp_path: Path) -> None:
    async with make_client(tmp_path) as client:
        response = await client.get("/")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["content-security-policy"] == (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )


@pytest.mark.anyio
async def test_openapi_docs_csp_allows_swagger_assets_without_weakening_webui(tmp_path: Path) -> None:
    async with make_client(tmp_path) as client:
        docs = await client.get("/docs")
        webui = await client.get("/")

    assert docs.status_code == 200
    docs_csp = docs.headers["content-security-policy"]
    assert "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'" in docs_csp
    assert "style-src 'self' https://cdn.jsdelivr.net" in docs_csp
    assert webui.headers["content-security-policy"] == (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )


@pytest.mark.anyio
async def test_capabilities_describe_the_active_injected_provider_set(tmp_path: Path) -> None:
    from tests.test_sessions_pipeline import providers

    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"), providers=providers()
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/capabilities")

    active = {item["stage"]: item for item in response.json()["providers"]}
    assert active["vad"]["name"] == "Voice"
    assert active["asr"]["name"] == "Words"
    assert active["asr"]["name"] != "deterministic-development-asr"


@pytest.mark.anyio
async def test_http_and_validation_failures_use_stable_error_envelope(tmp_path: Path) -> None:
    async with make_client(tmp_path) as client:
        missing = await client.get("/api/v1/does-not-exist")
        invalid = await client.get("/api/v1/health?verbose=not-a-bool")

    assert missing.status_code == 404
    assert missing.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "stage": None,
            "retryable": False,
            "details": {},
        }
    }
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert invalid.json()["error"]["retryable"] is False


@pytest.mark.anyio
async def test_unexpected_failures_use_sanitized_stable_error_envelope(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime")
    app = create_app(settings)

    def broken_list() -> list[object]:
        raise RuntimeError("private database detail")

    app.state.speakers.list = broken_list
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/speakers")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "stage": None,
            "retryable": False,
            "details": {},
        }
    }
    assert "private database detail" not in response.text


@pytest.mark.anyio
async def test_openapi_is_grouped_and_explains_beginner_inputs_outputs(tmp_path: Path) -> None:
    async with make_client(tmp_path) as client:
        schema = (await client.get("/openapi.json")).json()

    assert "local speech processing API" in schema["info"]["description"]
    tags = {tag["name"]: tag["description"] for tag in schema["tags"]}
    assert {"System", "Conversation Flow", "Audio Stages", "Text Stages", "Speakers", "Audio Artifacts"} <= set(tags)

    correct = schema["paths"]["/api/v1/text/correct"]["post"]
    assert correct["summary"] == "Correct recognized text"
    assert "Input" in correct["description"] and "Output" in correct["description"]
    text_schema = schema["components"]["schemas"]["TextInput"]["properties"]["text"]
    assert text_schema["description"]
    assert text_schema["examples"] == ["請幫我整理今天的工作重點"]

    vad = schema["paths"]["/api/v1/audio/vad"]["post"]
    wav_body = vad["requestBody"]["content"]["audio/wav"]["schema"]
    assert "PCM WAV" in wav_body["description"]
    assert "200" in vad["responses"]

    artifact = schema["paths"]["/api/v1/artifacts/{name}"]["get"]["responses"]["200"]
    assert artifact["content"] == {
        "audio/wav": {"schema": {"type": "string", "format": "binary"}}
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("locale", "expected_summary", "expected_validation_message"),
    [
        ("en", "Check service health", "Human-readable validation error message."),
        ("zh-TW", "檢查服務健康狀態", "便於閱讀的驗證錯誤訊息。"),
        ("ja", "サービスの稼働状態を確認", "読みやすい validation error message。"),
        ("ko", "서비스 상태 확인", "사람이 읽을 수 있는 validation 오류 메시지."),
    ],
)
async def test_openapi_localizes_every_supported_language(
    tmp_path: Path, locale: str, expected_summary: str, expected_validation_message: str
) -> None:
    async with make_client(tmp_path) as client:
        schema = (await client.get(f"/openapi.json?lang={locale}")).json()

    assert schema["paths"]["/api/v1/health"]["get"]["summary"] == expected_summary
    storage = schema["components"]["schemas"]["HealthResponse"]["properties"]["storage_ready"]
    assert storage["description"]
    validation_message = schema["components"]["schemas"]["ValidationError"]["properties"]["msg"]
    assert validation_message["description"] == expected_validation_message


@pytest.mark.anyio
async def test_openapi_defaults_and_unknown_locales_fall_back_to_english(tmp_path: Path) -> None:
    async with make_client(tmp_path) as client:
        default = (await client.get("/openapi.json")).json()
        unknown = (await client.get("/openapi.json?lang=not-supported")).json()

    assert default["info"]["description"].startswith("Agent Speak is a local speech processing API")
    assert unknown["info"] == default["info"]
    assert unknown["paths"]["/api/v1/text/correct"]["post"]["summary"] == "Correct recognized text"


@pytest.mark.anyio
async def test_localized_openapi_documents_keep_the_same_machine_contract(tmp_path: Path) -> None:
    async with make_client(tmp_path) as client:
        schemas = {
            locale: (await client.get(f"/openapi.json?lang={locale}")).json()
            for locale in ("en", "zh-TW", "ja", "ko")
        }

    english = schemas["en"]
    expected_paths = {
        path: set(methods).intersection({"get", "post", "patch", "delete", "put"})
        for path, methods in english["paths"].items()
    }
    expected_components = {
        name: {
            "required": tuple(schema.get("required", [])),
            "properties": tuple(schema.get("properties", {})),
        }
        for name, schema in english["components"]["schemas"].items()
    }
    for schema in schemas.values():
        assert {
            path: set(methods).intersection({"get", "post", "patch", "delete", "put"})
            for path, methods in schema["paths"].items()
        } == expected_paths
        assert {
            name: {
                "required": tuple(component.get("required", [])),
                "properties": tuple(component.get("properties", {})),
            }
            for name, component in schema["components"]["schemas"].items()
        } == expected_components
        for methods in schema["paths"].values():
            for method, operation in methods.items():
                if method in {"get", "post", "patch", "delete", "put"}:
                    assert operation["summary"]
                    assert operation["description"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("locale", "frozen_phrase", "default_phrase"),
    [
        ("en", "frozen for the session", "configured server default"),
        ("zh-TW", "工作階段固定", "伺服器設定的預設語言"),
        ("ja", "session に固定", "server 設定の既定言語"),
        ("ko", "session에 고정", "server 설정 기본 언어"),
    ],
)
async def test_openapi_localizes_session_speech_language_contract(
    tmp_path: Path,
    locale: str,
    frozen_phrase: str,
    default_phrase: str,
) -> None:
    async with make_client(tmp_path) as client:
        schema = (await client.get(f"/openapi.json?lang={locale}")).json()

    create = schema["paths"]["/api/v1/sessions"]["post"]
    parameter = next(item for item in create["parameters"] if item["name"] == "speech_language")
    field = schema["components"]["schemas"]["SessionSummary"]["properties"]["speech_language"]
    asr = schema["paths"]["/api/v1/audio/asr"]["post"]

    assert frozen_phrase in create["description"]
    assert frozen_phrase in parameter["description"]
    assert frozen_phrase in field["description"]
    assert parameter["schema"]["enum"] == ["auto", "en", "zh-TW", "ja", "ko"]
    assert field["examples"] == ["zh-TW"]
    assert default_phrase in asr["description"]


@pytest.mark.anyio
@pytest.mark.parametrize("locale", ["en", "zh-TW", "ja", "ko"])
async def test_openapi_describes_frozen_session_model_contract(
    tmp_path: Path, locale: str
) -> None:
    async with make_client(tmp_path) as client:
        schema = (await client.get(f"/openapi.json?lang={locale}")).json()

    create = schema["paths"]["/api/v1/sessions"]["post"]
    parameters = {item["name"]: item for item in create["parameters"]}
    summary = schema["components"]["schemas"]["SessionSummary"]["properties"]

    assert parameters["asr_model"]["schema"]["enum"] == [
        "faster-whisper-small",
        "breeze-asr-25",
        "qwen3-asr-1.7b",
    ]
    assert parameters["correction_model"]["schema"]["enum"] == [
        "qwen2.5-correction",
        "disabled",
    ]
    assert parameters["asr_model"]["description"]
    assert parameters["correction_model"]["description"]
    assert summary["asr_model"]["examples"] == ["qwen3-asr-1.7b"]
    assert summary["correction_model"]["examples"] == ["qwen2.5-correction"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("locale", "catalog_summary", "activation_summary", "field_phrase"),
    [
        ("en", "View available inference models", "Switch active inference models", "Stable ASR model identifier"),
        ("zh-TW", "查看可用推論模型", "切換啟用中的推論模型", "穩定的 ASR 模型識別碼"),
        ("ja", "利用可能な推論モデルを表示", "有効な推論モデルを切り替え", "安定した ASR モデル ID"),
        ("ko", "사용 가능한 추론 모델 보기", "활성 추론 모델 전환", "안정적인 ASR 모델 ID"),
    ],
)
async def test_openapi_fully_localizes_model_control_contract(
    tmp_path: Path,
    locale: str,
    catalog_summary: str,
    activation_summary: str,
    field_phrase: str,
) -> None:
    async with make_client(tmp_path) as client:
        schema = (await client.get(f"/openapi.json?lang={locale}")).json()

    catalog = schema["paths"]["/api/v1/models"]["get"]
    activation = schema["paths"]["/api/v1/models/active"]["put"]
    field = schema["components"]["schemas"]["ASRModelOption"]["properties"]["id"]

    assert catalog["summary"] == catalog_summary
    assert catalog["description"]
    assert activation["summary"] == activation_summary
    assert activation["description"]
    assert field_phrase in field["description"]
    for schema_name in ("ASRModelOption", "CorrectionModelOption", "ActiveModelSelection", "ModelCatalog", "ModelActivationInput"):
        assert all(item.get("description") for item in schema["components"]["schemas"][schema_name]["properties"].values())
