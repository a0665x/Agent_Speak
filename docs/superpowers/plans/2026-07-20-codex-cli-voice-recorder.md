# Codex CLI Voice Recorder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `/codex` page that gates recording on visible Zone Vibe 100 input/output devices, records with separate start/stop controls, transcribes and corrects through existing APIs, and copies corrected text for pasting into the current Codex CLI session.

**Architecture:** FastAPI serves four new local static assets without changing `/api/v1`. A small dependency-free JavaScript core owns pure device matching and button-state rules, while a browser controller owns permissions, MediaRecorder, WAV conversion, API calls, rendering, and clipboard fallback. Python route/contract tests plus executable Node core tests provide hardware-free regression coverage.

**Tech Stack:** FastAPI/Starlette responses, build-free HTML/CSS/JavaScript, browser MediaDevices/MediaRecorder/Web Audio/Clipboard APIs, pytest/httpx ASGI tests, Node `assert`.

---

## File structure

- Create `web/codex.html`: semantic Traditional Chinese recorder page and fixed DOM hooks.
- Create `web/codex.css`: isolated responsive/accessibility styling for the compact recorder.
- Create `web/codex-recorder-core.js`: pure headset matching, timer formatting, and control-state functions usable by browser and Node.
- Create `web/codex.js`: browser controller for health, permission-gated discovery, recording, WAV conversion, ASR, correction, and clipboard.
- Create `tests/codex_recorder_core.test.js`: executable Node behavioral tests for the pure core.
- Modify `src/agent_speak/app.py`: serve `/codex` and the three new static assets.
- Modify `tests/test_webui.py`: verify delivery, CSP-safe local assets, DOM contract, API hooks, limits, and safe text rendering.
- Modify `scripts/test.sh`: syntax-check both recorder scripts and execute the Node behavioral test.
- Modify `spec/UI.md`: document the dedicated Codex CLI clipboard workflow and headset gate.
- Modify `spec/TESTING.md`: document automated and real-headset acceptance commands.

### Task 1: Serve the dedicated recorder shell

**Files:**
- Modify: `tests/test_webui.py`
- Modify: `src/agent_speak/app.py:181-227`
- Create: `web/codex.html`
- Create: `web/codex.css`
- Create: `web/codex-recorder-core.js`
- Create: `web/codex.js`

- [ ] **Step 1: Write the failing delivery and markup tests**

Append to `tests/test_webui.py`:

```python
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
    assert 'id="start-recording-button"' in page.text
    assert 'id="stop-recording-button"' in page.text
    assert 'id="start-recording-button" type="button" disabled' in page.text
    assert 'id="stop-recording-button" type="button" disabled' in page.text
    assert 'id="raw-transcript"' in page.text
    assert 'id="corrected-text"' in page.text
    assert 'id="copy-text-button"' in page.text
    assert "https://" not in page.text and "http://" not in page.text
    assert css.headers["content-type"].startswith("text/css")
    assert core.headers["content-type"].startswith("text/javascript")
    assert javascript.headers["content-type"].startswith("text/javascript")
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_webui.py::test_codex_recorder_and_local_assets_are_served
```

Expected: FAIL because `GET /codex` returns the error envelope for 404.

- [ ] **Step 3: Add minimal routes and semantic page assets**

Add routes beside the current web routes in `src/agent_speak/app.py`:

```python
    @app.get("/codex", include_in_schema=False)
    async def codex_recorder() -> Response:
        return Response(content=(web_dir / "codex.html").read_text(encoding="utf-8"), media_type="text/html")

    @app.get("/static/codex.css", include_in_schema=False)
    async def codex_styles() -> Response:
        return Response(content=(web_dir / "codex.css").read_text(encoding="utf-8"), media_type="text/css")

    @app.get("/static/codex-recorder-core.js", include_in_schema=False)
    async def codex_recorder_core() -> Response:
        return Response(content=(web_dir / "codex-recorder-core.js").read_text(encoding="utf-8"), media_type="text/javascript")

    @app.get("/static/codex.js", include_in_schema=False)
    async def codex_script() -> Response:
        return Response(content=(web_dir / "codex.js").read_text(encoding="utf-8"), media_type="text/javascript")
```

Create `web/codex.html` with a single compact card. It must load only local assets in this order:

```html
<link rel="stylesheet" href="/static/codex.css">
<script src="/static/codex-recorder-core.js" defer></script>
<script src="/static/codex.js" defer></script>
```

The main controls must be literal semantic buttons:

```html
<button id="device-check-button" type="button">檢查 Zone Vibe 100 裝置</button>
<button id="start-recording-button" type="button" disabled>開始錄音</button>
<button id="stop-recording-button" type="button" disabled>結束錄音</button>
<button id="copy-text-button" type="button" hidden>複製校正文字</button>
```

Include `role="status" aria-live="polite"` for gateway, device, recording, and clipboard status; read-only output blocks with IDs `raw-transcript` and `corrected-text`; and visible wording that text is copied for manual paste/Enter rather than automatically submitted to Codex.

Create the minimal boot assets needed for the route test to turn green:

```javascript
// web/codex-recorder-core.js
"use strict";
globalThis.AgentSpeakCodexRecorder = {};
```

```javascript
// web/codex.js
"use strict";
```

Create `web/codex.css` with local system fonts, a 720 px maximum card, 48 px minimum controls, `:focus-visible`, disabled styles, `@media (max-width: 600px)`, `overflow-x: hidden`, and `@media (prefers-reduced-motion: reduce)`. Do not use external `url(...)` assets.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the focused pytest command from Step 2.

Expected: PASS.

- [ ] **Step 5: Commit the shell**

```bash
git add src/agent_speak/app.py tests/test_webui.py web/codex.html web/codex.css web/codex-recorder-core.js web/codex.js
git commit -m "feat: add Codex voice recorder page"
```

### Task 2: Implement and test the hardware gate state model

**Files:**
- Create: `tests/codex_recorder_core.test.js`
- Modify: `web/codex-recorder-core.js`
- Modify: `scripts/test.sh:11-16`

- [ ] **Step 1: Write failing pure behavioral tests**

Create `tests/codex_recorder_core.test.js`:

```javascript
"use strict";
const assert = require("node:assert/strict");
const core = require("../web/codex-recorder-core.js");

const devices = [
  { kind: "audioinput", deviceId: "mic-zone", label: "Logitech Zone Vibe 100 Hands-Free" },
  { kind: "audiooutput", deviceId: "speaker-zone", label: "Zone Vibe 100" },
  { kind: "audioinput", deviceId: "laptop", label: "Built-in Audio" },
];

assert.deepEqual(core.findZoneVibeDevices(devices), {
  input: devices[0],
  output: devices[1],
});
assert.deepEqual(core.findZoneVibeDevices(devices.slice(0, 1)), {
  input: devices[0],
  output: null,
});
assert.equal(core.hasRequiredDevices(core.findZoneVibeDevices(devices)), true);
assert.equal(core.hasRequiredDevices(core.findZoneVibeDevices(devices.slice(0, 1))), false);
assert.deepEqual(core.controlsForState("unchecked", false), { checkDisabled: false, startDisabled: true, stopDisabled: true });
assert.deepEqual(core.controlsForState("ready", true), { checkDisabled: false, startDisabled: false, stopDisabled: true });
assert.deepEqual(core.controlsForState("recording", true), { checkDisabled: true, startDisabled: true, stopDisabled: false });
assert.deepEqual(core.controlsForState("processing", true), { checkDisabled: true, startDisabled: true, stopDisabled: true });
assert.equal(core.formatTimer(7), "00:07 / 00:30");
assert.equal(core.formatTimer(30), "00:30 / 00:30");
console.log("CODEX_RECORDER_CORE_TESTS_OK");
```

- [ ] **Step 2: Run the Node test and verify RED**

Run:

```bash
node tests/codex_recorder_core.test.js
```

Expected: FAIL because the exported functions do not exist.

- [ ] **Step 3: Implement the minimal pure core**

Replace `web/codex-recorder-core.js` with a UMD-style dependency-free core:

```javascript
"use strict";
(function expose(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.AgentSpeakCodexRecorder = api;
}(typeof globalThis === "object" ? globalThis : this, function buildCore() {
  const TARGET = "zone vibe 100";
  function normalizeDeviceLabel(label) {
    return String(label || "").trim().toLowerCase().replace(/\s+/g, " ");
  }
  function findZoneVibeDevices(devices) {
    const list = Array.from(devices || []);
    const matches = (kind) => list.find((device) => device.kind === kind && normalizeDeviceLabel(device.label).includes(TARGET)) || null;
    return { input: matches("audioinput"), output: matches("audiooutput") };
  }
  function hasRequiredDevices(pair) {
    return Boolean(pair && pair.input && pair.output);
  }
  function controlsForState(state, devicesReady) {
    return {
      checkDisabled: state === "checking" || state === "recording" || state === "processing",
      startDisabled: state !== "ready" || !devicesReady,
      stopDisabled: state !== "recording",
    };
  }
  function formatTimer(seconds) {
    const bounded = Math.max(0, Math.min(30, Math.floor(Number(seconds) || 0)));
    return `00:${String(bounded).padStart(2, "0")} / 00:30`;
  }
  return { normalizeDeviceLabel, findZoneVibeDevices, hasRequiredDevices, controlsForState, formatTimer };
}));
```

- [ ] **Step 4: Run the Node test and verify GREEN**

Run the Node command from Step 2.

Expected: `CODEX_RECORDER_CORE_TESTS_OK`.

- [ ] **Step 5: Add the Node regression to the project test runner**

Extend the Node branch in `scripts/test.sh`:

```bash
  node --check web/app.js
  node --check web/codex-recorder-core.js
  node --check web/codex.js
  node tests/codex_recorder_core.test.js
```

- [ ] **Step 6: Run the project test script focused on WebUI**

Run:

```bash
./scripts/test.sh -q tests/test_webui.py
```

Expected: pytest passes, `CODEX_RECORDER_CORE_TESTS_OK`, then `TESTS_OK pytest_passed`.

- [ ] **Step 7: Commit the hardware-gate core**

```bash
git add web/codex-recorder-core.js tests/codex_recorder_core.test.js scripts/test.sh
git commit -m "test: cover Codex recorder device gate"
```

### Task 3: Implement device discovery and recording controls

**Files:**
- Modify: `tests/test_webui.py`
- Modify: `web/codex.js`

- [ ] **Step 1: Write a failing browser-controller contract test**

Append to `tests/test_webui.py`:

```python
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
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_webui.py::test_codex_recorder_gates_capture_on_zone_vibe_input_and_output
```

Expected: FAIL because `web/codex.js` is still empty.

- [ ] **Step 3: Implement the controller state and device check**

In `web/codex.js`, bind all DOM nodes with `querySelector`, import functions from `globalThis.AgentSpeakCodexRecorder`, and keep this state:

```javascript
const MAX_RECORDING_SECONDS = 30;
const MAX_AUDIO_BYTES = 8 * 1024 * 1024;
const state = {
  phase: "unchecked", devices: { input: null, output: null },
  stream: null, recorder: null, chunks: [], autoStopTimer: null,
  timerInterval: null, startedAt: 0,
};
```

Implement `renderControls()` exclusively through `controlsForState`. Implement `checkDevices()` so it:

1. Rejects missing `mediaDevices`, `getUserMedia`, `enumerateDevices`, or `MediaRecorder` with a compatibility error.
2. Enters `checking`.
3. Opens a temporary `{audio: true}` permission stream from the button click.
4. Calls `enumerateDevices()` after permission is granted.
5. Stops every temporary track in `finally`.
6. Uses `findZoneVibeDevices` and renders input/output missing states separately.
7. Enters `ready` only when `hasRequiredDevices` is true.

Register `navigator.mediaDevices.addEventListener("devicechange", invalidateDevices)` when available. `invalidateDevices` clears the stored pair, enters `unchecked`, and states that the operator must check again.

- [ ] **Step 4: Implement explicit start/stop recording**

`startRecording()` must request only the matched input:

```javascript
state.stream = await navigator.mediaDevices.getUserMedia({
  audio: { deviceId: { exact: state.devices.input.deviceId } },
});
state.recorder = new MediaRecorder(state.stream);
state.chunks = [];
state.recorder.addEventListener("dataavailable", (event) => {
  if (event.data && event.data.size) state.chunks.push(event.data);
});
state.recorder.addEventListener("stop", processRecording, { once: true });
state.recorder.start();
state.autoStopTimer = setTimeout(stopRecording, MAX_RECORDING_SECONDS * 1000);
```

`stopRecording()` clears both timers, changes to `processing`, calls `MediaRecorder.stop()` only when active, and stops every stream track. The timer uses `formatTimer` and never exceeds 30 seconds. Start and stop handlers must be registered only on their explicit buttons.

- [ ] **Step 5: Run the focused test and verify GREEN**

Run the focused pytest command from Step 2, then:

```bash
node --check web/codex.js
node tests/codex_recorder_core.test.js
```

Expected: all commands pass.

- [ ] **Step 6: Commit device discovery and recording controls**

```bash
git add tests/test_webui.py web/codex.js
git commit -m "feat: gate Codex recording on headset devices"
```

### Task 4: Add WAV, ASR, correction, and clipboard flow

**Files:**
- Modify: `tests/test_webui.py`
- Modify: `web/codex.js`

- [ ] **Step 1: Write the failing processing contract test**

Append to `tests/test_webui.py`:

```python
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
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_webui.py::test_codex_recorder_transcribes_corrects_and_copies_without_agent_or_tts
```

Expected: FAIL because WAV conversion and API calls are absent.

- [ ] **Step 3: Implement bounded WAV conversion**

Implement `validateAudioSize(blob)`, `decodeToMono(blob)`, and `encodeWav(samples, sampleRate)`. `decodeToMono` uses `AudioContext.decodeAudioData`; stereo/multichannel input is averaged sample by sample. `encodeWav` writes RIFF/WAVE, mono, PCM format 1, 16-bit samples with clamping to `[-1, 1]`. Validate the MediaRecorder source blob and converted WAV against `MAX_AUDIO_BYTES`.

The returned blob must be:

```javascript
new Blob([view.buffer], { type: "audio/wav" })
```

- [ ] **Step 4: Implement stable API error handling**

Add:

```javascript
async function readJson(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error?.message || `HTTP ${response.status}`);
    error.code = body.error?.code || "request_failed";
    throw error;
  }
  return body;
}
```

`processRecording()` converts the chunks, POSTs the WAV with `Content-Type: audio/wav`, validates non-empty `asr.text`, then POSTs `{text: asr.text}` as JSON to correction and validates non-empty `corrected.text`. Use only `textContent` to render both results.

- [ ] **Step 5: Implement clipboard success and fallback**

After corrected text is rendered, attempt:

```javascript
try {
  await navigator.clipboard.writeText(corrected.text);
  elements.clipboardStatus.textContent = "校正文字已複製；請回到 Codex CLI 貼上並按 Enter。";
  elements.copy.hidden = true;
} catch (error) {
  elements.clipboardStatus.textContent = "瀏覽器未允許自動複製，請按下方按鈕。";
  elements.copy.hidden = false;
}
```

The manual copy handler calls `navigator.clipboard.writeText(elements.correctedText.textContent)` and reports success only after the promise resolves. Errors retain the corrected text and keep the copy action available.

In all processing exits, stop audio tracks, clear timers, and return to `ready` only if the previously checked device pair is still valid. Do not copy an empty string.

- [ ] **Step 6: Run the processing test and full WebUI suite**

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_webui.py
node --check web/codex-recorder-core.js
node --check web/codex.js
node tests/codex_recorder_core.test.js
```

Expected: pytest passes and Node prints `CODEX_RECORDER_CORE_TESTS_OK`.

- [ ] **Step 7: Commit the processing flow**

```bash
git add tests/test_webui.py web/codex.js
git commit -m "feat: copy corrected speech for Codex CLI"
```

### Task 5: Document and verify the completed feature

**Files:**
- Modify: `spec/UI.md`
- Modify: `spec/TESTING.md`

- [ ] **Step 1: Add documentation assertions first**

Append a test to `tests/test_docs.py` that reads both spec files and asserts these durable contract phrases exist:

```python
def test_codex_voice_recorder_is_documented() -> None:
    ui = Path("spec/UI.md").read_text(encoding="utf-8")
    testing = Path("spec/TESTING.md").read_text(encoding="utf-8")
    assert "`/codex`" in ui
    assert "Zone Vibe 100" in ui
    assert "clipboard" in ui.lower()
    assert "Codex CLI" in testing
    assert "physical playback" in testing
```

- [ ] **Step 2: Run the documentation test and verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_docs.py::test_codex_voice_recorder_is_documented
```

Expected: FAIL because the two spec documents do not yet describe `/codex`.

- [ ] **Step 3: Update the focused specs**

Add to `spec/UI.md`:

- `/codex` is a separate beginner-focused Codex CLI clipboard recorder.
- Start remains disabled until the browser sees both Zone Vibe 100 input and output.
- Device checking does not record or play sound.
- Stop performs bounded WAV → ASR → correction → clipboard, and paste/Enter remains explicit.
- Clipboard denial exposes a manual copy control.

Add to `spec/TESTING.md`:

- `tests/test_webui.py` covers delivery and browser integration hooks.
- `node tests/codex_recorder_core.test.js` covers device matching and state rules.
- Manual acceptance requires the operator to grant browser microphone permission, verify both labels, explicitly record, inspect transcript/correction, and paste into Codex CLI.
- Enumeration is not proof of physical playback; no playback claim is made.

- [ ] **Step 4: Run the documentation test and verify GREEN**

Run the focused command from Step 2.

Expected: PASS.

- [ ] **Step 5: Run complete verification**

Run:

```bash
./scripts/test.sh
git diff --check
```

Expected: complete pytest suite passes, JavaScript checks pass, `CODEX_RECORDER_CORE_TESTS_OK` and `TESTS_OK pytest_passed` are printed, and `git diff --check` is silent.

If Docker Compose is available outside the current Snap-restricted execution environment, additionally run:

```bash
./run.sh --test
./run.sh --status
```

Expected: `TESTS_OK` and `GATEWAY_READY`/healthy status. Do not report these Docker checks as passing when they cannot execute.

- [ ] **Step 6: Commit documentation and final regression**

```bash
git add tests/test_docs.py spec/UI.md spec/TESTING.md scripts/test.sh tests/codex_recorder_core.test.js
git commit -m "docs: document Codex recorder verification"
```

- [ ] **Step 7: Hand off real-headset acceptance without starting hardware**

Tell the operator to open `http://127.0.0.1:8765/codex`, press `檢查 Zone Vibe 100 裝置`, verify the exact displayed input/output labels, press `開始錄音`, speak, press `結束錄音`, inspect both text fields, then paste into the current Codex CLI. Only the operator's button presses may start microphone capture; the implementation does not play audio.
