from pathlib import Path

import httpx
import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings


@pytest.mark.anyio
async def test_asr_realtime_is_canonical_and_old_route_redirects(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        canonical = await client.get("/asr_realtime")
        legacy = await client.get("/realtime")
        worklet = await client.get("/asr_realtime/pcm-capture.worklet.js")
    assert canonical.status_code == 200
    assert '<div id="root"></div>' in canonical.text
    assert legacy.status_code in {307, 308}
    assert legacy.headers["location"] == "/asr_realtime"
    assert worklet.headers["content-type"].startswith(("text/javascript", "application/javascript"))


@pytest.mark.anyio
async def test_legacy_realtime_worklet_redirects_to_canonical_path(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        worklet = await client.get("/realtime/pcm-capture.worklet.js")
    assert worklet.status_code in {307, 308}
    assert worklet.headers["location"] == "/asr_realtime/pcm-capture.worklet.js"


@pytest.mark.anyio
async def test_root_is_project_guide_without_capture_controls(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = (await client.get("/")).text
        javascript = (await client.get("/static/app.js")).text

    assert '<html lang="en">' in page
    assert 'id="language-select"' in page
    assert "Make every step of speech visible." in page
    assert 'href="#main"' in page
    assert all(target in page for target in ('data-route="/docs"', 'data-route="/asr_realtime"', 'id="system-status"'))
    assert all(label in page for label in ("API Explorer", "ASR Realtime", "System Status"))
    assert all(stage in page for stage in ("VAD", "Endpoint", "ASR", "Correction"))
    assert "getUserMedia" not in javascript
    assert "MediaRecorder" not in javascript
    assert "WebSocket" not in javascript
    assert 'fetch("/api/v1/health")' in javascript
    assert 'fetch("/api/v1/capabilities")' in javascript
    assert "innerHTML" not in javascript
    assert 'src="/static/locale.js"' in page
    assert 'id="particle-field"' in page
    assert 'data-profile="hero"' in page
    assert 'src="/static/particle-field.js"' in page


@pytest.mark.anyio
async def test_project_guide_local_assets_are_served(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        css = await client.get("/static/app.css")
        javascript = await client.get("/static/app.js")
        locale = await client.get("/static/locale.js")
        particles = await client.get("/static/particle-field.js")
        artwork = await client.get("/static/speech-core-hero.png")

    assert css.headers["content-type"].startswith("text/css")
    assert javascript.headers["content-type"].startswith("text/javascript")
    assert locale.headers["content-type"].startswith("text/javascript")
    assert particles.status_code == 200
    assert particles.headers["content-type"].startswith("text/javascript")
    assert "createParticleLayout" in particles.text
    assert artwork.status_code == 200
    assert artwork.headers["content-type"] == "image/png"


@pytest.mark.anyio
async def test_webui_css_has_accessible_responsive_and_motion_contract(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        css = (await client.get("/static/app.css")).text

    assert "--ice:" in css
    assert "--violet:" in css
    assert "min-height: 44px" in css
    assert ":focus-visible" in css
    assert "@media (max-width: 700px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (prefers-reduced-transparency: reduce)" in css
    assert "@media (prefers-contrast: more)" in css
    assert "overflow-x: hidden" in css
    assert "line-height: .94" in css
    assert "letter-spacing: -.038em" in css

    asr_css = Path("frontend/realtime/src/styles.css").read_text(encoding="utf-8")
    assert "line-height: .90" in asr_css
    assert "letter-spacing: -.038em" in asr_css
    assert ".ambient-particles" in asr_css and "opacity: .92" in asr_css


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("query", "locale", "label"),
    [
        ("", "en", "API language"),
        ("?lang=zh-TW", "zh-TW", "API 語言"),
        ("?lang=ja", "ja", "API の言語"),
        ("?lang=ko", "ko", "API 언어"),
        ("?lang=unsupported", "en", "API language"),
    ],
)
async def test_docs_language_selector_loads_the_localized_openapi_document(
    tmp_path: Path, query: str, locale: str, label: str
) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = await client.get(f"/docs{query}")

    assert page.status_code == 200
    assert f'<html lang="{locale}">' in page.text
    assert 'id="language-select"' in page.text
    assert f'aria-label="{label}"' in page.text
    assert f'data-current-locale="{locale}"' in page.text
    assert f'url: "/openapi.json?lang={locale}"' in page.text
    assert 'href="/static/docs-locale.css"' in page.text
    assert 'src="/static/docs-locale.js"' in page.text
    for option in ('value="en"', 'value="zh-TW"', 'value="ja"', 'value="ko"'):
        assert option in page.text


@pytest.mark.anyio
async def test_docs_language_assets_are_local_and_interactive(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        script = await client.get("/static/docs-locale.js")
        style = await client.get("/static/docs-locale.css")

    assert script.headers["content-type"].startswith("text/javascript")
    assert style.headers["content-type"].startswith("text/css")
    assert "agent-speak-locale" in script.text
    assert "window.location.assign" in script.text
    assert "min-height: 44px" in style.text
    assert ":focus-visible" in style.text


@pytest.mark.anyio
async def test_codex_recorder_and_local_assets_are_served(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = await client.get("/codex")
        css = await client.get("/static/codex.css")
        core = await client.get("/static/codex-recorder-core.js")
        javascript = await client.get("/static/codex.js")

    assert page.status_code == 200
    assert '<html lang="zh-Hant-TW">' in page.text
    assert 'id="device-check-button"' in page.text
    assert 'id="start-recording-button" type="button" disabled' in page.text
    assert 'id="stop-recording-button" type="button" disabled' in page.text
    assert 'id="raw-transcript"' in page.text
    assert 'id="corrected-text"' in page.text
    assert 'id="copy-text-button"' in page.text
    assert "https://" not in page.text and "http://" not in page.text
    assert css.headers["content-type"].startswith("text/css")
    assert core.headers["content-type"].startswith("text/javascript")
    assert javascript.headers["content-type"].startswith("text/javascript")


@pytest.mark.anyio
async def test_codex_recorder_gates_capture_on_default_input_and_output(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        javascript = (await client.get("/static/codex.js")).text

    required = (
        "navigator.mediaDevices.getUserMedia",
        "navigator.mediaDevices.enumerateDevices",
        "findDefaultAudioDevices",
        "hasRequiredDevices",
        'addEventListener("devicechange"',
        'audio: { deviceId: { exact: state.devices.input.deviceId } }',
        "new MediaRecorder",
        "MAX_RECORDING_SECONDS = 30",
        "setTimeout(stopRecording, MAX_RECORDING_SECONDS * 1000)",
        "clearTimeout(state.autoStopTimer)",
    )
    assert all(item in javascript for item in required)
    assert "shell" not in javascript


@pytest.mark.anyio
async def test_codex_recorder_transcribes_corrects_and_copies_without_agent_or_tts(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        javascript = (await client.get("/static/codex.js")).text

    required = (
        "decodeAudioData",
        "encodeWav",
        "MAX_AUDIO_BYTES = 8 * 1024 * 1024",
        'fetch("/api/v1/audio/asr"',
        'fetch("/api/v1/text/correct"',
        '"Content-Type": "audio/wav"',
        '"Content-Type": "application/json"',
        "navigator.clipboard.writeText",
        "elements.rawTranscript.textContent",
        "elements.correctedText.textContent",
        "elements.copy.hidden = false",
    )
    assert all(item in javascript for item in required)
    assert "/api/v1/agent/respond" not in javascript
    assert "/api/v1/tts/synthesize" not in javascript
    assert "innerHTML" not in javascript
