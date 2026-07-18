from pathlib import Path

import httpx
import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings


@pytest.mark.anyio
async def test_operator_console_and_local_assets_are_served(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = await client.get("/")
        css = await client.get("/static/app.css")
        javascript = await client.get("/static/app.js")

    assert page.status_code == 200
    assert '<html lang="en">' in page.text
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in page.text
    assert 'href="#main"' in page.text
    assert 'id="record-button"' in page.text
    assert 'aria-live="polite"' in page.text
    assert 'id="turn-state" role="status" aria-live="polite"' in page.text
    assert all(stage in page.text for stage in ("VAD", "ASR", "Correction", "Endpoint", "Agent", "TTS"))
    assert all(section in page.text for section in ("Transcript", "Response", "Capabilities", "Speaker profiles"))
    assert "https://" not in page.text and "http://" not in page.text
    assert css.headers["content-type"].startswith("text/css")
    assert javascript.headers["content-type"].startswith("text/javascript")


@pytest.mark.anyio
async def test_webui_css_has_accessible_responsive_and_reduced_motion_contract(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        css = (await client.get("/static/app.css")).text

    assert "--accent:" in css
    assert "--paper:" in css
    assert "min-height: 48px" in css
    assert ":focus-visible" in css
    assert "@media (max-width: 600px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "overflow-x: hidden" in css
    assert ".content-grid { display: grid; grid-template-columns: 1fr;" in css
    assert ".side-stack { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert "url(" not in css


@pytest.mark.anyio
async def test_webui_javascript_wires_recording_pipeline_and_speakers(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        javascript = (await client.get("/static/app.js")).text

    required_hooks = (
        "navigator.mediaDevices.getUserMedia",
        "MediaRecorder",
        "decodeAudioData",
        "encodeWav",
        "WebSocket",
        "/api/v1/sessions",
        "/turns",
        "/api/v1/capabilities",
        "/api/v1/speakers",
        "/samples",
        "/match",
        "setTimeout(connectEvents",
        "lastSequence",
        "/api/v1/speakers/${state.selectedSpeaker}",
    )
    assert all(hook in javascript for hook in required_hooks)
    assert "Content-Type\": \"audio/wav" in javascript
    assert "innerHTML" not in javascript


@pytest.mark.anyio
async def test_webui_enforces_capture_bounds_and_disables_both_ingress_controls(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = (await client.get("/")).text
        javascript = (await client.get("/static/app.js")).text

    assert "MAX_RECORDING_SECONDS = 30" in javascript
    assert "MAX_AUDIO_BYTES = 8 * 1024 * 1024" in javascript
    assert "setTimeout(stopRecording, MAX_RECORDING_SECONDS * 1000)" in javascript
    assert "clearTimeout(state.recordingTimer)" in javascript
    assert "validateAudioSize(file)" in javascript
    assert "validateAudioSize(wav)" in javascript
    assert "elements.record.disabled = disabled" in javascript
    assert "elements.upload.disabled = disabled" in javascript
    assert "30 seconds" in page
    assert "8 MiB" in page


@pytest.mark.anyio
async def test_capture_toggle_targets_the_explicit_upload_label(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = (await client.get("/")).text
        javascript = (await client.get("/static/app.js")).text

    assert 'id="audio-upload-label"' in page
    assert 'uploadLabel: document.querySelector("#audio-upload-label")' in javascript
    assert 'elements.uploadLabel.setAttribute("aria-disabled", String(disabled))' in javascript
    assert 'elements.upload.closest("label")' not in javascript
