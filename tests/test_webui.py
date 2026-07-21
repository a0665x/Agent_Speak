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
async def test_real_speech_capabilities_have_localized_non_tone_descriptions(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        javascript = (await client.get("/static/app.js")).text

    assert '"Faster-Whisper local transcription; CPU inference.": "limitationWhisper"' in javascript
    assert '"Piper local Mandarin speech synthesis.": "limitationPiper"' in javascript
    assert 'limitationWhisper: "本機 Faster-Whisper 語音辨識（CPU 推論）。"' in javascript
    assert 'limitationPiper: "本機 Piper 中文語音合成。"' in javascript


@pytest.mark.anyio
async def test_operator_console_and_local_assets_are_served(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = await client.get("/")
        css = await client.get("/static/app.css")
        javascript = await client.get("/static/app.js")

    assert page.status_code == 200
    assert '<html lang="zh-Hant-TW">' in page.text
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in page.text
    assert 'href="#main"' in page.text
    assert 'id="record-button"' in page.text
    assert 'aria-live="polite"' in page.text
    assert 'id="turn-state" role="status" aria-live="polite"' in page.text
    assert all(stage in page.text for stage in ("VAD", "ASR", "Correction", "Endpoint", "Agent", "TTS"))
    assert all(section in page.text for section in ("辨識文字", "Agent 回覆", "目前能力", "說話者資料"))
    assert "https://" not in page.text and "http://" not in page.text
    assert css.headers["content-type"].startswith("text/css")
    assert javascript.headers["content-type"].startswith("text/javascript")


@pytest.mark.anyio
async def test_webui_defaults_to_traditional_chinese_with_persistent_english_switch(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = (await client.get("/")).text
        javascript = (await client.get("/static/app.js")).text

    assert 'id="language-toggle"' in page
    assert 'aria-label="切換語言"' in page
    assert "開始錄音" in page
    assert "English" in page
    assert 'const DEFAULT_LOCALE = "zh-TW"' in javascript
    assert 'localStorage.getItem("agent-speak-locale")' in javascript
    assert 'localStorage.setItem("agent-speak-locale", locale)' in javascript
    assert 'document.documentElement.lang = currentLocale === "zh-TW" ? "zh-Hant-TW" : "en"' in javascript
    assert 'elements.transcript.removeAttribute("data-i18n")' in javascript
    assert 'elements.response.removeAttribute("data-i18n")' in javascript
    assert "function readStoredLocale()" in javascript
    assert "function writeStoredLocale(locale)" in javascript
    assert "state.speakerResultFactory" in javascript
    assert "state.actionErrorFactory" in javascript


@pytest.mark.anyio
async def test_webui_explains_the_beginner_workflow_and_each_major_area(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = (await client.get("/")).text

    assert 'aria-labelledby="quick-start-title"' in page
    assert all(step in page for step in ("錄音或上傳", "觀察處理流程", "查看文字與回覆"))
    assert "先從這裡開始" in page
    assert "這裡會依序顯示語音如何被處理" in page
    assert "進階功能" in page
    assert "名詞小抄" in page
    assert all(term in page for term in ("VAD", "ASR", "TTS"))


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
    assert "30 秒" in page
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
async def test_codex_recorder_gates_capture_on_zone_vibe_input_and_output(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        javascript = (await client.get("/static/codex.js")).text

    required = (
        "navigator.mediaDevices.getUserMedia",
        "navigator.mediaDevices.enumerateDevices",
        "findZoneVibeDevices",
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
