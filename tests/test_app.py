from pathlib import Path

import httpx
import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings


def make_client(tmp_path: Path) -> httpx.AsyncClient:
    settings = Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime")
    app = create_app(settings)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


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
    ("locale", "expected_summary"),
    [
        ("en", "Check service health"),
        ("zh-TW", "檢查服務健康狀態"),
        ("ja", "サービスの稼働状態を確認"),
        ("ko", "서비스 상태 확인"),
    ],
)
async def test_openapi_localizes_every_supported_language(
    tmp_path: Path, locale: str, expected_summary: str
) -> None:
    async with make_client(tmp_path) as client:
        schema = (await client.get(f"/openapi.json?lang={locale}")).json()

    assert schema["paths"]["/api/v1/health"]["get"]["summary"] == expected_summary
    storage = schema["components"]["schemas"]["HealthResponse"]["properties"]["storage_ready"]
    assert storage["description"]


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
