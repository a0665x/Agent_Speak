# Multi-Model Realtime ASR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generic default audio-device detection, session-frozen hot-swappable ASR/correction policies, explicit model preparation, and a layered realtime audio visualization.

**Architecture:** Keep one ASR provider resident behind a dedicated worker-owned model manager. The Gateway exposes additive model catalog/activation endpoints and freezes model IDs into each session; the React client stops, activates, creates a new session, and resumes without a Submit button. Model downloads remain an explicit, idempotent `./run.sh --models` operation backed by a pinned manifest and private model volume.

**Tech Stack:** FastAPI, Pydantic, httpx, asyncio/thread offload, Faster-Whisper/CTranslate2, PyTorch, Transformers, `qwen-asr`, Docker Compose, Bash, React 19, TypeScript, Canvas 2D, Vitest, pytest.

**Approved design:** `spec/references/20260722-multi-model-realtime-design.md`

---

## File structure

New backend units:

- `src/agent_speak/model_ids.py`: public ASR/correction literals, defaults, and display metadata.
- `src/agent_speak/asr_providers.py`: Breeze and Qwen adapters implementing the existing bounded-WAV ASR behavior.
- `src/agent_speak/asr_model_manager.py`: single-resident activation state, lease, unload, warm-up, rollback, and status snapshots.
- `src/agent_speak/model_control.py`: Gateway-facing model catalog service and remote worker control client.

New frontend units:

- `frontend/realtime/src/models.ts`: model IDs, storage, API types, and pure switch-state helpers.
- `frontend/realtime/src/components/ActiveModels.tsx`: accessible ASR/correction selectors and activation progress.
- `frontend/realtime/src/audio/signalRibbons.ts`: pure smoothing and ribbon geometry helpers.

Existing files retain their current responsibility. Do not move unrelated provider, session, or UI code.

### Task 1: Freeze model choices into sessions

**Files:**
- Create: `src/agent_speak/model_ids.py`
- Modify: `src/agent_speak/schemas.py`
- Modify: `src/agent_speak/sessions.py`
- Modify: `src/agent_speak/app.py`
- Modify: `src/agent_speak/locales.py`
- Test: `tests/test_sessions_pipeline.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write failing session model tests**

Add tests that create sessions with all approved model IDs, verify the defaults,
verify `session.created`, and reject unknown IDs:

```python
@pytest.mark.parametrize("asr_model", [
    "faster-whisper-small", "breeze-asr-25", "qwen3-asr-1.7b",
])
async def test_session_freezes_asr_model(tmp_path: Path, asr_model: str) -> None:
    app = create_app(settings=test_settings(tmp_path))
    async with app_client(app) as client:
        response = await client.post("/api/v1/sessions", params={"asr_model": asr_model})
    assert response.status_code == 201
    assert response.json()["asr_model"] == asr_model
    assert response.json()["events"][0]["data"]["asr_model"] == asr_model

async def test_session_model_defaults_are_qwen_asr_and_qwen_correction(tmp_path: Path) -> None:
    app = create_app(settings=test_settings(tmp_path))
    async with app_client(app) as client:
        response = await client.post("/api/v1/sessions")
    assert response.json()["asr_model"] == "qwen3-asr-1.7b"
    assert response.json()["correction_model"] == "qwen2.5-correction"
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_sessions_pipeline.py tests/test_app.py
```

Expected: failures report missing `asr_model`/`correction_model` fields and query parameters.

- [ ] **Step 3: Add strict model IDs and immutable session fields**

Implement the exact public types in `model_ids.py`:

```python
from typing import Literal

ASRModelId = Literal["faster-whisper-small", "breeze-asr-25", "qwen3-asr-1.7b"]
CorrectionModelId = Literal["qwen2.5-correction", "disabled"]
DEFAULT_ASR_MODEL: ASRModelId = "qwen3-asr-1.7b"
DEFAULT_CORRECTION_MODEL: CorrectionModelId = "qwen2.5-correction"
```

Add both fields to `SessionSummary`, `SessionBroker.create`, the create-session route, and `session.created`. Extend all four OpenAPI locale catalogs with complete parameter and response-field descriptions. Do not alter `speech_language` behavior.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit the session contract**

```bash
git add src/agent_speak/model_ids.py src/agent_speak/schemas.py src/agent_speak/sessions.py src/agent_speak/app.py src/agent_speak/locales.py tests/test_sessions_pipeline.py tests/test_app.py
git commit -m "feat: freeze inference models per session"
```

### Task 2: Add provider adapters for Breeze and Qwen3-ASR

**Files:**
- Create: `src/agent_speak/asr_providers.py`
- Modify: `src/agent_speak/production.py`
- Test: `tests/test_asr_providers.py`
- Test: `tests/test_production_providers.py`

- [ ] **Step 1: Write failing adapter contract tests**

Use injected processors/models so tests need no weights or GPU:

```python
def test_breeze_adapter_decodes_pcm_wav_and_returns_text() -> None:
    model = FakeWhisperModel(text="今天 deploy 新的 API")
    provider = BreezeASR(model_path=Path("/models/breeze"), model_factory=lambda **_: model)
    assert provider.transcribe(wav_bytes(), language="zh") == "今天 deploy 新的 API"

def test_qwen_adapter_maps_language_and_returns_first_result() -> None:
    model = FakeQwenModel(language="Chinese", text="請 review 這個 patch")
    provider = Qwen3ASR(model_path=Path("/models/qwen3"), model_factory=lambda **_: model)
    assert provider.transcribe(wav_bytes(), language="zh") == "請 review 這個 patch"
    assert model.requested_language == "Chinese"
```

Also test `auto → None`, `en → English`, `ja → Japanese`, `ko → Korean`, empty output, invalid WAV, and provider exception mapping.

- [ ] **Step 2: Run adapter tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_asr_providers.py tests/test_production_providers.py
```

Expected: import failure for `agent_speak.asr_providers`.

- [ ] **Step 3: Implement the two bounded adapters**

Both adapters expose:

```python
class ASRProvider(Protocol):
    device: str
    def warm(self) -> None: raise NotImplementedError
    def close(self) -> None: raise NotImplementedError
    def transcribe(self, audio: bytes, language: str | None = None) -> str: raise NotImplementedError
```

Decode input only through `decode_wav`; convert to mono float32/16k arrays. Breeze loads `AutoProcessor` and `AutoModelForSpeechSeq2Seq` from the pinned local directory with `local_files_only=True`. Qwen loads `Qwen3ASRModel.from_pretrained` from the pinned local directory and passes `(samples, 16000)` plus the mapped language. NVIDIA uses `torch.float16`; CPU uses `torch.float32`. No adapter may download at runtime.

Add `close()` to Faster-Whisper that clears its cached model reference. Provider exceptions become bounded `PlatformError` responses without local paths.

- [ ] **Step 4: Run adapter tests and verify GREEN**

Run Step 2. Expected: all adapter/provider tests pass without network or GPU.

- [ ] **Step 5: Commit provider adapters**

```bash
git add src/agent_speak/asr_providers.py src/agent_speak/production.py tests/test_asr_providers.py tests/test_production_providers.py
git commit -m "feat: add breeze and qwen asr providers"
```

### Task 3: Implement the single-resident ASR model manager

**Files:**
- Create: `src/agent_speak/asr_model_manager.py`
- Test: `tests/test_asr_model_manager.py`

- [ ] **Step 1: Write failing manager state/lease tests**

Cover initial activation, same-model idempotence, lease conflicts, unload-before-load, progress snapshots, warm failure rollback, rollback failure, and release ownership:

```python
def test_conflicting_activation_is_rejected_while_leased() -> None:
    manager = manager_with_fake_factories()
    manager.activate("qwen3-asr-1.7b")
    manager.acquire("session-a", "qwen3-asr-1.7b")
    with pytest.raises(ModelLeaseConflict):
        manager.activate("breeze-asr-25")

def test_failed_warm_restores_last_ready_provider() -> None:
    manager = manager_with_fake_factories(fail_warm={"breeze-asr-25"})
    manager.activate("qwen3-asr-1.7b")
    with pytest.raises(PlatformError):
        manager.activate("breeze-asr-25")
    assert manager.snapshot().active_asr_model == "qwen3-asr-1.7b"
    assert manager.snapshot().state == "ready"
```

- [ ] **Step 2: Run manager tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_asr_model_manager.py
```

Expected: import failure for the new manager.

- [ ] **Step 3: Implement manager state and rollback**

Define frozen snapshots with exact states:

```python
ModelLoadState = Literal["unavailable", "idle", "unloading", "loading", "warming", "ready", "failed", "rollback"]

@dataclass(frozen=True, slots=True)
class ModelManagerSnapshot:
    state: ModelLoadState
    active_asr_model: ASRModelId | None
    requested_asr_model: ASRModelId | None
    leased_by: str | None
    device: str
    error_code: str | None
```

Protect activation/transcription/lease mutation with one lock. Close and delete the old provider, call `gc.collect()`, and call `torch.cuda.empty_cache()` only when CUDA is available. Warm the new provider before publishing it as active. On failure, reconstruct and warm the previous provider; report unavailable if rollback also fails.

- [ ] **Step 4: Run manager tests and verify GREEN**

Run Step 2. Expected: all manager tests pass.

- [ ] **Step 5: Commit model manager**

```bash
git add src/agent_speak/asr_model_manager.py tests/test_asr_model_manager.py
git commit -m "feat: manage one resident asr model"
```

### Task 4: Expose internal worker control and public model API

**Files:**
- Modify: `src/agent_speak/asr_worker.py`
- Create: `src/agent_speak/model_control.py`
- Modify: `src/agent_speak/app.py`
- Modify: `src/agent_speak/schemas.py`
- Modify: `src/agent_speak/locales.py`
- Test: `tests/test_asr_worker.py`
- Create: `tests/test_model_control.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing internal/public API tests**

Test these contracts:

```python
response = await client.put("/api/v1/models/active", json={
    "asr_model": "breeze-asr-25",
    "correction_model": "disabled",
})
assert response.status_code in {200, 202}

catalog = (await client.get("/api/v1/models")).json()
assert catalog["active"]["asr_model"] == "breeze-asr-25"
assert {item["id"] for item in catalog["asr"]} == {
    "faster-whisper-small", "breeze-asr-25", "qwen3-asr-1.7b",
}
```

Also assert unknown IDs return 422, active lease returns stable HTTP 409 `model_in_use`, public errors contain no paths, and internal health reports manager state.

- [ ] **Step 2: Run API tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_asr_worker.py tests/test_model_control.py tests/test_app.py
```

Expected: 404 for `/api/v1/models` and missing internal activation routes.

- [ ] **Step 3: Add worker endpoints and Gateway control service**

Internal worker endpoints:

```text
GET  /internal/v1/models
PUT  /internal/v1/models/active
POST /internal/v1/models/lease/{session_id}
DELETE /internal/v1/models/lease/{session_id}
POST /internal/v1/asr?mode={mode}&speech_language={language}&asr_model={model_id}
```

The activation endpoint creates one tracked background activation task and returns 202 while it runs. The status endpoint reads the immutable manager snapshot. The Gateway remote client uses bounded httpx timeouts and response-size/error mapping. Public responses combine worker ASR state with correction choices; `disabled` is always selectable and Qwen correction readiness follows actual capabilities.

- [ ] **Step 4: Run API tests and verify GREEN**

Run Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit model-control APIs**

```bash
git add src/agent_speak/asr_worker.py src/agent_speak/model_control.py src/agent_speak/app.py src/agent_speak/schemas.py src/agent_speak/locales.py tests/test_asr_worker.py tests/test_model_control.py tests/test_app.py
git commit -m "feat: expose bounded model activation api"
```

### Task 5: Propagate model leases and correction policy through realtime

**Files:**
- Modify: `src/agent_speak/realtime_queue.py`
- Modify: `src/agent_speak/realtime.py`
- Modify: `src/agent_speak/realtime_routes.py`
- Modify: `src/agent_speak/remote_asr.py`
- Modify: `src/agent_speak/realtime_models.py`
- Test: `tests/test_realtime.py`
- Test: `tests/test_realtime_queue.py`
- Test: `tests/test_realtime_websocket.py`
- Test: `tests/test_remote_asr.py`

- [ ] **Step 1: Write failing propagation and bypass tests**

```python
async def test_realtime_uses_frozen_models_and_releases_lease() -> None:
    session = await broker.create(asr_model="breeze-asr-25", correction_model="disabled")
    stream = await orchestrator.open(session.id, session.speech_language, session.asr_model, session.correction_model)
    await stream.close()
    assert control.acquired == [(session.id, "breeze-asr-25")]
    assert control.released == [session.id]

async def test_disabled_correction_completes_with_raw_final_asr() -> None:
    result = await run_realtime_utterance(correction_model="disabled", final_text="raw text")
    assert result.completed_text == "raw text"
    assert correction.calls == []
```

Assert every ASR queue job carries `asr_model`, every completion event carries both model IDs, and a stream/session mismatch raises a programming error.

- [ ] **Step 2: Run realtime tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_realtime.py tests/test_realtime_queue.py tests/test_realtime_websocket.py tests/test_remote_asr.py
```

Expected: signatures and queue records lack model fields.

- [ ] **Step 3: Implement frozen propagation and lease lifecycle**

Acquire before accepting `stream.start`; release in the stream's idempotent close/finally path. Pass ASR model on every internal worker request. When correction is disabled, emit the normal correction-processing/completion sequence with explicit `policy=disabled` metadata and unchanged text so UI state remains deterministic.

- [ ] **Step 4: Run realtime tests and verify GREEN**

Run Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit realtime propagation**

```bash
git add src/agent_speak/realtime_queue.py src/agent_speak/realtime.py src/agent_speak/realtime_routes.py src/agent_speak/remote_asr.py src/agent_speak/realtime_models.py tests/test_realtime.py tests/test_realtime_queue.py tests/test_realtime_websocket.py tests/test_remote_asr.py
git commit -m "feat: route frozen models through realtime"
```

### Task 6: Build a pinned, atomic model downloader

**Files:**
- Rewrite: `scripts/bootstrap_models.py`
- Modify: `tests/test_model_bootstrap.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing manifest/preflight tests**

Create fakes for disk usage and downloads. Cover exact revisions, Breeze allow patterns, cached skip, insufficient space, non-zero required files, partial cleanup limited to the current operation, and atomic rename:

```python
def test_manifest_excludes_breeze_optimizer_and_duplicate_pt() -> None:
    entry = model_manifest()["breeze-asr-25"]
    assert "model.safetensors" in entry.allow_patterns
    assert "optimizer.bin" not in entry.allow_patterns
    assert not any(pattern.endswith(".pt") for pattern in entry.allow_patterns)

def test_preflight_preserves_existing_models_when_space_is_low(tmp_path: Path) -> None:
    existing = tmp_path / "qwen" / "keep.gguf"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"keep")
    with pytest.raises(ModelSpaceError):
        download_all(tmp_path, free_bytes=1, downloader=fake_downloader)
    assert existing.read_bytes() == b"keep"
```

- [ ] **Step 2: Run bootstrap tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_model_bootstrap.py
```

Expected: manifest/preflight functions do not exist.

- [ ] **Step 3: Implement pinned manifest and CLI modes**

Support:

```text
python scripts/bootstrap_models.py --verify
python scripts/bootstrap_models.py --download-all
```

Use the four approved Hugging Face revisions from the design. Download snapshots with `local_dir` and allow-listed inference files. Download Piper through `piper.download_voices` into its own partial directory. Require estimated missing bytes plus temporary overhead plus an 8GB safety reserve. Resolve every target under `/app/models`; remove only a partial directory created by the current invocation.

- [ ] **Step 4: Run bootstrap tests and verify GREEN**

Run Step 2. Expected: all bootstrap tests pass without network.

- [ ] **Step 5: Commit downloader**

```bash
git add scripts/bootstrap_models.py tests/test_model_bootstrap.py .gitignore
git commit -m "feat: add pinned atomic model downloads"
```

### Task 7: Add `run.sh --models` and dedicated ASR runtime image

**Files:**
- Modify: `run.sh`
- Modify: `Dockerfile`
- Modify: `compose.yaml`
- Modify: `compose.gpu.yaml`
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `docker/entrypoint.sh`
- Modify: `tests/test_docker_runtime.py`

- [ ] **Step 1: Write failing Docker/runtime contract tests**

Assert help includes `--models`, the option builds/runs only the downloader, normal startup uses `--verify`, Gateway/test targets do not install ASR-heavy extras, ASR target does, and Compose never mounts Docker socket:

```python
def test_run_models_is_explicit_and_normal_start_is_verify_only() -> None:
    script = (ROOT / "run.sh").read_text()
    assert "--models" in script
    assert "--download-all" in script
    assert "--verify" in script
    assert "/var/run/docker.sock" not in (ROOT / "compose.yaml").read_text()
```

- [ ] **Step 2: Run Docker contract tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_docker_runtime.py
```

Expected: `--models` assertions fail.

- [ ] **Step 3: Implement targets and lifecycle option**

Create a small `model-downloader` target containing Hugging Face/Piper download tools and an `asr-runtime` target containing the pinned PyTorch/Transformers/`qwen-asr` stack. Make `asr-worker` use `asr-runtime`; keep Gateway/test on the existing runtime target. `./run.sh --models` prepares directories, builds the downloader, and runs `--download-all`. Compose model-bootstrap runs `--verify` only.

Remove entrypoint lazy Piper downloads. Missing models fail with a concise `run ./run.sh --models` message. Extend the environment whitelist only with documented model-path/default IDs; never import arbitrary `.env` content.

- [ ] **Step 4: Run Docker contract tests and shell syntax checks**

```bash
.venv/bin/pytest -q tests/test_docker_runtime.py
bash -n run.sh scripts/setup.sh docker/entrypoint.sh
```

Expected: tests pass and shell syntax commands exit 0.

- [ ] **Step 5: Commit lifecycle/runtime changes**

```bash
git add run.sh Dockerfile compose.yaml compose.gpu.yaml pyproject.toml .env.example docker/entrypoint.sh tests/test_docker_runtime.py
git commit -m "feat: prepare all speech models explicitly"
```

### Task 8: Generalize browser audio-device detection

**Files:**
- Modify: `frontend/realtime/src/audio/deviceGate.ts`
- Modify: `frontend/realtime/src/audio/realtimeClient.ts`
- Modify: `frontend/realtime/src/components/DeviceGate.tsx`
- Modify: `frontend/realtime/src/audio/deviceGate.test.ts`
- Modify: `frontend/realtime/src/audio/realtimeClient.test.ts`
- Modify: `frontend/realtime/src/i18n.tsx`
- Modify: `src/agent_speak/config.py`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `spec/UI.md`
- Modify: `tests/test_docs.py`
- Modify: `tests/test_realtime_models.py`

- [ ] **Step 1: Replace brand-specific tests with generic default-device tests**

```typescript
it('prefers browser default input and output without a brand filter', async () => {
  const devices = mediaDevices([
    device('audioinput', 'usb-mic', 'USB microphone'),
    device('audioinput', 'default', 'Default — Bluetooth headset microphone'),
    device('audiooutput', 'default', 'Default — Bluetooth headset audio'),
  ]);
  const result = await checkAudioDevices(devices);
  expect(result.ready).toBe(true);
  expect(result.input?.deviceId).toBe('default');
  expect(result.output?.deviceId).toBe('default');
});
```

Add fallback-first-labeled, missing input/output, permission denial, temporary-track cleanup, and devicechange invalidation cases. Make docs tests fail if active source/README contains `Zone Vibe 100`.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
docker compose -f compose.yaml run --rm --no-deps frontend-test npm test -- src/audio/deviceGate.test.ts src/audio/realtimeClient.test.ts
.venv/bin/pytest -q tests/test_docs.py tests/test_realtime_models.py
```

Expected: old expected-label behavior and strings fail.

- [ ] **Step 3: Implement generic selection and localized copy**

Change `checkAudioDevices(mediaDevices)` to select default then first labeled per kind. Remove `realtime_expected_device` configuration entirely. DeviceGate heading becomes localized “Audio devices” and always displays actual labels. Keep exact input-device capture and existing output-visibility disclaimer.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run Step 2. Expected: selected tests pass and brand-string scan is clean outside historical design/plan files.

- [ ] **Step 5: Commit device generalization**

```bash
git add frontend/realtime/src/audio/deviceGate.ts frontend/realtime/src/audio/realtimeClient.ts frontend/realtime/src/components/DeviceGate.tsx frontend/realtime/src/audio/deviceGate.test.ts frontend/realtime/src/audio/realtimeClient.test.ts frontend/realtime/src/i18n.tsx src/agent_speak/config.py .env.example README.md spec/UI.md tests/test_docs.py tests/test_realtime_models.py
git commit -m "feat: detect generic default audio devices"
```

### Task 9: Add ACTIVE MODELS controls and automatic resume workflow

**Files:**
- Create: `frontend/realtime/src/models.ts`
- Create: `frontend/realtime/src/models.test.ts`
- Create: `frontend/realtime/src/components/ActiveModels.tsx`
- Create: `frontend/realtime/src/components/ActiveModels.test.tsx`
- Modify: `frontend/realtime/src/App.tsx`
- Modify: `frontend/realtime/src/App.test.tsx`
- Modify: `frontend/realtime/src/i18n.tsx`
- Modify: `frontend/realtime/src/styles.css`
- Modify: `frontend/realtime/src/types.ts`
- Modify: `frontend/realtime/src/state/reducer.ts`
- Modify: `frontend/realtime/src/state/reducer.test.ts`
- Modify: `frontend/realtime/src/components/TranscriptPanel.tsx`
- Modify: `frontend/realtime/src/components/UtteranceGraph.tsx`
- Modify: `frontend/realtime/src/components/UtteranceGraph.test.tsx`

- [ ] **Step 1: Write failing pure-state and component tests**

Test API parsing, persisted selection, unavailable options, selector lock while loading, and the exact automatic workflow:

```typescript
it('stops, activates, creates a frozen session, and resumes', async () => {
  render(<App services={fakeServices({ active: true })} />);
  await user.selectOptions(screen.getByLabelText('ASR model'), 'breeze-asr-25');
  expect(calls).toEqual([
    'stop:model_change',
    'activate:breeze-asr-25:qwen2.5-correction',
    'wait:ready',
    'create-session:breeze-asr-25:qwen2.5-correction',
    'start:new-session',
  ]);
});
```

Also test load failure/no resume, rollback messaging, device invalidation/no resume, disabled correction, rapid selector lock, completed row preservation, partial removal, and immutable model attribution on graph hover.

- [ ] **Step 2: Run frontend tests and verify RED**

```bash
docker compose -f compose.yaml run --rm --no-deps frontend-test npm test
```

Expected: missing models module/components and workflow assertions fail.

- [ ] **Step 3: Implement model state and ACTIVE MODELS card**

Use exact frontend IDs matching `model_ids.py`. Fetch catalog on mount and after activation. Persist ASR/correction selections separately from locale/language. On change, disable both selects, stop if active, clear partial rows only, PUT active models, poll with bounded backoff until ready/failed, recheck `gate.ready`, create a session with language and both model query parameters, then resume.

Do not reset completed rows or completed graph IDs. Add `asrModel` and `correctionModel` to row metadata at completion. Render compact model badges and escaped tooltip metadata. All new copy must exist in `en`, `zh-TW`, `ja`, and `ko`.

- [ ] **Step 4: Run frontend tests and TypeScript build**

```bash
docker compose -f compose.yaml run --rm --no-deps frontend-test npm test
docker compose -f compose.yaml run --rm --no-deps frontend-test npm run build
```

Expected: all frontend tests pass and Vite build exits 0.

- [ ] **Step 5: Commit model controls**

```bash
git add frontend/realtime/src
git commit -m "feat: switch realtime models without submit"
```

### Task 10: Replace the line chart with layered signal ribbons

**Files:**
- Create: `frontend/realtime/src/audio/signalRibbons.ts`
- Create: `frontend/realtime/src/audio/signalRibbons.test.ts`
- Modify: `frontend/realtime/src/components/AudioStage.tsx`
- Create: `frontend/realtime/src/components/AudioStage.test.tsx`
- Modify: `frontend/realtime/src/styles.css`

- [ ] **Step 1: Write failing geometry/render tests**

```typescript
it('smooths real envelope energy without inventing nonzero speech', () => {
  expect(smoothEnvelope([0, 0, 0], 7)).toEqual([0, 0, 0, 0, 0, 0, 0]);
  expect(Math.max(...smoothEnvelope([0, 1, 0], 7))).toBeGreaterThan(0);
});

it('draws two gradient ribbons and honors reduced motion', () => {
  const draw = vi.fn();
  render(<AudioStage samples={[0, .2, .8, .1]} state="speech" reducedMotion draw={draw} />);
  expect(draw).toHaveBeenCalledWith(expect.objectContaining({ ribbonCount: 2, animate: false }));
});
```

Also test clamping, stable center line, HiDPI resize, and empty/idle envelope behavior.

- [ ] **Step 2: Run waveform tests and verify RED**

```bash
docker compose -f compose.yaml run --rm --no-deps frontend-test npm test -- src/audio/signalRibbons.test.ts src/components/AudioStage.test.tsx
```

Expected: missing geometry module and new AudioStage API.

- [ ] **Step 3: Implement C-style layered ribbons**

Use a bounded ring of recent samples, exponential smoothing, cubic interpolation, two phase-offset centerline paths, and ice-blue/violet CanvasGradient strokes. Energy controls amplitude and glow alpha. Idle samples remain zero. Recreate the backing store on CSS-size/devicePixelRatio changes. Reduced motion disables phase drift and glow pulsing but still redraws new real samples.

- [ ] **Step 4: Run waveform tests and full frontend suite**

```bash
docker compose -f compose.yaml run --rm --no-deps frontend-test npm test
docker compose -f compose.yaml run --rm --no-deps frontend-test npm run build
```

Expected: suite and build pass.

- [ ] **Step 5: Commit signal ribbons**

```bash
git add frontend/realtime/src/audio/signalRibbons.ts frontend/realtime/src/audio/signalRibbons.test.ts frontend/realtime/src/components/AudioStage.tsx frontend/realtime/src/components/AudioStage.test.tsx frontend/realtime/src/styles.css
git commit -m "feat: render layered live audio ribbons"
```

### Task 11: Synchronize docs, Skill, OpenAPI, and progressive specs

**Files:**
- Modify: `README.md`
- Modify: `skills/agent-speak/SKILL.md`
- Modify: `spec/ARCHITECTURE.md`
- Modify: `spec/API.md`
- Modify: `spec/RUNTIME.md`
- Modify: `spec/SKILL_AND_MCP.md`
- Modify: `spec/TESTING.md`
- Modify: `spec/UI.md`
- Modify: `spec/project_herness.md`
- Modify: `docs/OPENAPI_QUICKSTART_ZH_TW.md`
- Modify: `tests/test_docs.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing documentation/OpenAPI assertions**

Assert all four localized OpenAPI documents describe the two model parameters and model endpoints, README quickstart runs `--models` before build, Skill preserves consent and standalone behavior, and active user docs contain no branded headset requirement.

- [ ] **Step 2: Run documentation tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_docs.py tests/test_app.py
```

Expected: new contract text/metadata assertions fail.

- [ ] **Step 3: Update every contract surface**

Document exact model IDs/defaults, single-resident load behavior, correction disabled semantics, `--models`, pinned/private artifacts, generic device visibility, 409 lease conflict, rollback, and no automatic hardware use. Mark the design reference Implemented only after integration acceptance passes.

- [ ] **Step 4: Run documentation tests and verify GREEN**

Run Step 2. Expected: all docs/OpenAPI tests pass.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md skills/agent-speak/SKILL.md spec docs/OPENAPI_QUICKSTART_ZH_TW.md tests/test_docs.py tests/test_app.py
git commit -m "docs: explain multi-model realtime operation"
```

### Task 12: Download, build, and execute production integration acceptance

**Files:**
- Create: `scripts/model_smoke.py`
- Create: `tests/test_model_smoke.py`
- Modify: `Dockerfile`
- Test: `tests/test_production_providers.py`
- Update after acceptance: `spec/references/20260722-multi-model-realtime-design.md`

- [ ] **Step 1: Write a failing hardware-free test for the production smoke client**

The smoke client accepts injected HTTP/WebSocket transports in tests and uses
real localhost transports from its CLI. It synthesizes one committed phrase,
then runs that bounded WAV through all model IDs and both correction policies:

```python
def test_model_smoke_cycles_models_and_correction_policies() -> None:
    transport = FakeSmokeTransport(transcript="今天 deploy 新的 API")
    result = run_model_smoke(
        transport,
        asr_models=("faster-whisper-small", "breeze-asr-25", "qwen3-asr-1.7b"),
        phrase="今天 deploy 新的 API",
    )
    assert result.models_passed == 3
    assert transport.activations == [
        "faster-whisper-small", "breeze-asr-25", "qwen3-asr-1.7b",
    ]
    assert transport.correction_policies == ["qwen2.5-correction", "disabled"]
```

- [ ] **Step 2: Run the smoke-client test and verify RED**

```bash
.venv/bin/pytest -q tests/test_model_smoke.py
```

Expected: import failure for `scripts.model_smoke`.

- [ ] **Step 3: Implement the bounded model smoke CLI**

Expose these types/functions so the test uses the same orchestration as the CLI:

```python
@dataclass(frozen=True, slots=True)
class ModelSmokeResult:
    models_passed: int
    enabled_text: str
    disabled_text: str

def run_model_smoke(
    transport: SmokeTransport,
    *,
    asr_models: Sequence[ASRModelId],
    phrase: str,
) -> ModelSmokeResult:
    transcripts: list[str] = []
    for model_id in asr_models:
        transport.activate(model_id, "qwen2.5-correction")
        transport.wait_ready(model_id, timeout_seconds=180)
        text = transport.transcribe_realtime(phrase, model_id, "qwen2.5-correction")
        if not text.strip():
            raise RuntimeError(f"empty transcript for {model_id}")
        transcripts.append(text)
    active = asr_models[-1]
    raw_text, disabled_text = transport.compare_correction_policies(phrase, active)
    if raw_text != disabled_text:
        raise RuntimeError("disabled correction changed final ASR text")
    return ModelSmokeResult(len(transcripts), transcripts[-1], disabled_text)
```

The localhost transport calls `PUT /api/v1/models/active`, polls
`GET /api/v1/models` with a bounded 180-second deadline, obtains a WAV from
`POST /api/v1/tts/synthesize`, and sends its PCM frames through a realtime
session/WebSocket. It waits for `utterance.completed`, asserts the event's model
ID, and keeps every response under existing byte/time limits. For the default
Qwen ASR it runs correction enabled and disabled and asserts disabled final text
equals its raw `asr.final` text. Print only:

```text
MODEL_SMOKE_OK models=3 correction=enabled,disabled
```

Do not print audio bytes or persist the generated WAV.

- [ ] **Step 4: Run smoke-client tests and verify GREEN**

```bash
.venv/bin/pytest -q tests/test_model_smoke.py tests/test_production_providers.py
```

Expected: all selected tests pass without network, models, or GPU.

- [ ] **Step 5: Run the complete hardware-free regression**

```bash
./run.sh --test
git diff --check
```

Expected: `TESTS_OK`, all backend/frontend tests pass, and diff check emits no output.

- [ ] **Step 6: Verify disk space and download pinned models**

```bash
df -h /home/nvidia/Desktop/Agent_Speak
./run.sh --models
./run.sh --models
```

Expected: first run downloads/verifies every manifest entry while preserving at least the configured reserve; second run reports every entry cached and performs no download.

- [ ] **Step 7: Build CPU and NVIDIA production paths**

```bash
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --build
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --rebuild
./run.sh --status
```

Expected: CPU build completes; NVIDIA rebuild reports `accelerator=nvidia`, ASR device CUDA, correction NVIDIA, and all services healthy. If disk preflight fails, stop and request user-directed cleanup; do not prune automatically.

- [ ] **Step 8: Run bounded WAV acceptance for all models**

```bash
docker compose -f compose.yaml -f compose.gpu.yaml exec -T gateway \
  python scripts/model_smoke.py --base-url http://127.0.0.1:8765
```

Expected: `MODEL_SMOKE_OK models=3 correction=enabled,disabled`. All models produce non-empty bounded transcripts with matching model metadata and no CUDA/OOM errors. No microphone permission or playback is used.

- [ ] **Step 9: Verify lease conflict through the production API**

Extend `scripts/model_smoke.py --check-lease-conflict` to keep one synthetic
realtime stream open, request a different ASR model, and assert HTTP 409 with
code `model_in_use`, then close the stream in `finally`:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml exec -T gateway \
  python scripts/model_smoke.py --base-url http://127.0.0.1:8765 --check-lease-conflict
```

Expected: the same `MODEL_SMOKE_OK` marker plus `lease_conflict=verified`.

- [ ] **Step 10: Verify the real browser without audio hardware activation**

Open `/asr_realtime?lang=en`; inspect desktop/mobile widths, console, horizontal overflow, default Qwen selection, model availability, localized selectors, keyboard focus, reduced motion, and idle zero-energy ribbons. Do not click Check Devices or Start Listening.

Expected: zero console errors, model state matches API, and no microphone permission prompt appears.

- [ ] **Step 11: Mark the approved design implemented and run final regression**

Change only the design status and verified evidence section after Steps 1–5 succeed, then run:

```bash
./run.sh --test
git diff --check
git status --short
```

Expected: `TESTS_OK`; only intended source/docs changes plus the pre-existing untracked `.superpowers/` appear. Model/runtime artifacts remain ignored.

- [ ] **Step 12: Commit verified integration state**

```bash
git add scripts/model_smoke.py tests/test_model_smoke.py Dockerfile tests/test_production_providers.py spec/references/20260722-multi-model-realtime-design.md
git commit -m "test: verify multi-model production runtime"
```

Stage only files that actually changed. Never stage `models/`, `runtime/`, `data/`, logs, recordings, credentials, or `.superpowers/`.

### Task 13: Optional consent-gated physical headset acceptance

**Files:** none unless a reproducible bug is found and handled through a new failing test.

- [ ] **Step 1: Ask for fresh explicit consent**

State that the next action will request browser microphone permission and record a bounded utterance. Do not proceed from prior general approval.

- [ ] **Step 2: If and only if approved, run one bounded realtime smoke**

Check devices, verify the displayed default input/output labels, Start Listening, speak one Mandarin-English sentence, Stop, and inspect VAD/ASR/endpoint/correction states plus transcript model attribution. Do not play speaker audio.

- [ ] **Step 3: Report hardware evidence accurately**

Separate browser enumeration, successful microphone capture, ASR output, and physical playback. Physical playback remains untested unless separately requested and consented.
