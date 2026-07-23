# VoxCPM2 TTS Clone Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GPU-exclusive VoxCPM2/vLLM-Omni TTS Clone Test with one ephemeral browser reference, explicit Generate/Play controls, complete runtime status, and no persistent voice data.

**Architecture:** The existing Gateway remains the public `/api/v1` boundary. A private Python 3.12 vLLM-Omni worker is active only in `tts` GPU mode, while the existing ASR and correction workers are active only in `asr` mode. A new React entry inside the existing frontend package owns browser capture, temporary Blob lifecycle, playback, and the state-reactive Voice Orb.

**Tech Stack:** FastAPI, Pydantic, HTTPX, NumPy PCM analysis, Docker Compose, vLLM 0.24.0, vLLM-Omni commit `b9e9d236c3f78afd405119a5b686ebebeeb53984` (release v0.24.1), VoxCPM2 revision `bffb3df5a29440629464e5e839f4d214c8714c3d`, React 19, TypeScript, Vite, Web Audio API, Vitest.

---

## File structure

New backend files:

- `src/agent_speak/tts_clone.py`: style-cue compilation, reference assessment, vLLM-Omni client, status/error normalization.
- `src/agent_speak/tts_clone_routes.py`: the three public TTS Clone endpoints and dependency wiring.
- `tests/test_tts_clone.py`: pure domain/client tests.
- `tests/test_tts_clone_api.py`: public API, privacy, output, and OpenAPI tests.

New frontend files:

- `frontend/realtime/tts-clone.html`: second Vite HTML entry.
- `frontend/realtime/vite.tts-clone.config.ts`: builds to `web/tts_clone_test`.
- `frontend/realtime/src/ttsClone/main.tsx`: React mount.
- `frontend/realtime/src/ttsClone/App.tsx`: page state machine and orchestration.
- `frontend/realtime/src/ttsClone/api.ts`: status, validation, and synthesis requests.
- `frontend/realtime/src/ttsClone/audio.ts`: capture, PCM WAV encoding, analyser samples, playback, and cleanup.
- `frontend/realtime/src/ttsClone/i18n.tsx`: complete `en`, `zh-TW`, `ja`, and `ko` catalog.
- `frontend/realtime/src/ttsClone/types.ts`: state and API types.
- `frontend/realtime/src/ttsClone/components/DeviceRuntimeGate.tsx`: microphone, speaker, GPU, worker, and model readiness.
- `frontend/realtime/src/ttsClone/components/VoiceOrb.tsx`: state-reactive Canvas 2D orb.
- `frontend/realtime/src/ttsClone/components/VoiceClonePanel.tsx`: reference recording and quality.
- `frontend/realtime/src/ttsClone/components/TTSPlayPanel.tsx`: text, cues, clone toggle, Generate, and Play.
- `frontend/realtime/src/ttsClone/styles.css`: responsive Apple-like graphite/ice/violet presentation.
- Co-located `*.test.ts(x)` files for every new frontend unit.

Modified integration files:

- `scripts/bootstrap_models.py`, `tests/test_model_bootstrap.py`
- `pyproject.toml`, `src/agent_speak/config.py`, `src/agent_speak/schemas.py`
- `src/agent_speak/app.py`, `src/agent_speak/locales.py`
- `Dockerfile`, `compose.yaml`, `compose.gpu.yaml`, `run.sh`, `.env.example`
- `frontend/realtime/package.json`
- `web/index.html`, `web/app.css`, `web/locale.js`
- `tests/test_app.py`, `tests/test_contracts.py`, `tests/test_docker_runtime.py`, `tests/test_webui.py`, `tests/portal_locale.test.js`
- `README.md`, `README.zh-TW.md`, `spec/PROJECT_MAP.md`, `spec/ARCHITECTURE.md`, `spec/API.md`, `spec/RUNTIME.md`, `spec/TESTING.md`, `spec/UI.md`, `spec/project_herness.md`

## Task 0: Preserve the verified pre-feature working tree

The repository already contains tested ASR reliability and structured-logging work from the previous request. It overlaps files required by this feature, so checkpoint it before TTS changes rather than mixing two features in later commits.

- [ ] **Step 1: Confirm the existing diff contains no private runtime material**

Run:

```sh
git status -sb
git diff --check
git diff --name-only
```

Expected: `.superpowers/` is untracked and no `models/`, `runtime/`, `data/`, logs, WAV, `.env`, or credential file appears.

- [ ] **Step 2: Re-run the existing baseline**

Run:

```sh
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --test
```

Expected: Python/recorder tests and 58 existing React tests pass with `TESTS_OK`.

- [ ] **Step 3: Commit only the already verified prior feature files**

Stage the files reported in the 2026-07-22 reliability/logging handoff, explicitly excluding `.superpowers/` and this TTS plan:

```sh
git add .env.example README.md README.zh-TW.md compose.yaml \
  frontend/realtime/src/App.test.tsx frontend/realtime/src/App.tsx \
  run.sh spec/PROJECT_MAP.md spec/RUNTIME.md spec/TESTING.md \
  spec/project_herness.md \
  spec/references/20260722-realtime-model-reliability-and-logging-design.md \
  spec/references/20260722-realtime-model-reliability-and-logging-plan.md \
  src/agent_speak/app.py src/agent_speak/asr_providers.py \
  src/agent_speak/asr_worker.py src/agent_speak/config.py \
  src/agent_speak/diagnostic_logging.py src/agent_speak/realtime.py \
  tests/test_app.py tests/test_asr_providers.py tests/test_asr_worker.py \
  tests/test_contracts.py tests/test_diagnostic_logging.py \
  tests/test_docker_runtime.py tests/test_realtime.py \
  web/asr_realtime/index.html web/asr_realtime/assets/index-DLmfRkLn.js \
  web/asr_realtime/assets/index-DmGfGNGu.js
git commit -m "fix: stabilize realtime model switching and diagnostics"
```

Expected: one commit; `.superpowers/` remains untracked.

## Task 1: Pin and prepare VoxCPM2

**Files:**

- Modify: `scripts/bootstrap_models.py`
- Modify: `tests/test_model_bootstrap.py`
- Modify: `.env.example`

- [ ] **Step 1: Write the failing manifest test**

Add to `tests/test_model_bootstrap.py`:

```python
def test_manifest_pins_voxcpm2_runtime_files() -> None:
    entry = model_manifest()["voxcpm2"]

    assert entry.repo_id == "openbmb/VoxCPM2"
    assert entry.revision == "bffb3df5a29440629464e5e839f4d214c8714c3d"
    assert entry.target == Path("tts/voxcpm2")
    assert entry.estimated_bytes == 9_600_000_000
    assert set(entry.required_files) == {
        "audiovae.pth",
        "config.json",
        "model.safetensors",
        "special_tokens_map.json",
        "tokenization_voxcpm2.py",
        "tokenizer.json",
        "tokenizer_config.json",
    }
```

Update the existing exact manifest-set assertion to include `"voxcpm2"`.

- [ ] **Step 2: Verify RED**

Run:

```sh
python -m pytest tests/test_model_bootstrap.py -q
```

Expected: failure because `voxcpm2` is absent.

- [ ] **Step 3: Add the pinned manifest entry**

Add this `ModelManifestEntry` in `model_manifest()`:

```python
ModelManifestEntry(
    model_id="voxcpm2",
    repo_id="openbmb/VoxCPM2",
    revision="bffb3df5a29440629464e5e839f4d214c8714c3d",
    target=Path("tts/voxcpm2"),
    estimated_bytes=9_600_000_000,
    allow_patterns=(
        "audiovae.pth",
        "config.json",
        "model.safetensors",
        "special_tokens_map.json",
        "tokenization_voxcpm2.py",
        "tokenizer.json",
        "tokenizer_config.json",
    ),
    required_files=(
        "audiovae.pth",
        "config.json",
        "model.safetensors",
        "special_tokens_map.json",
        "tokenization_voxcpm2.py",
        "tokenizer.json",
        "tokenizer_config.json",
    ),
),
```

Add `AGENT_SPEAK_VOXCPM2_MODEL_PATH=/app/models/tts/voxcpm2` to `.env.example`.

- [ ] **Step 4: Verify GREEN**

Run:

```sh
python -m pytest tests/test_model_bootstrap.py -q
```

Expected: all model-bootstrap tests pass.

- [ ] **Step 5: Commit**

```sh
git add scripts/bootstrap_models.py tests/test_model_bootstrap.py .env.example
git commit -m "feat: pin VoxCPM2 model preparation"
```

## Task 2: Build the bounded TTS Clone domain and vLLM adapter

**Files:**

- Create: `src/agent_speak/tts_clone.py`
- Create: `tests/test_tts_clone.py`
- Modify: `src/agent_speak/config.py`
- Modify: `tests/test_contracts.py`

- [ ] **Step 1: Write failing style and reference tests**

Create `tests/test_tts_clone.py` with tests for:

```python
def test_style_cues_compile_to_allowlisted_natural_language() -> None:
    assert compile_style_cues(["warm", "light_laugh"], "Hello") == (
        "(warm delivery, speaking with a light laugh)Hello"
    )
    with pytest.raises(PlatformError) as error:
        compile_style_cues(["[unknown]"], "Hello")
    assert error.value.code == "invalid_style_cue"


def test_reference_assessment_reports_good_voice() -> None:
    wav = voiced_wav(duration_seconds=10.0, amplitude=0.25)
    result = assess_reference(
        wav,
        max_bytes=8 * 1024 * 1024,
        rms_threshold=0.015,
    )
    assert result.quality == "good"
    assert result.duration_seconds == pytest.approx(10.0)
    assert result.voiced_ratio >= 0.9


@pytest.mark.parametrize(
    ("duration", "amplitude", "quality"),
    [(3.0, 0.2, "too_short"), (10.0, 0.001, "too_quiet"), (31.0, 0.2, "too_long")],
)
def test_reference_assessment_returns_bounded_quality(
    duration: float, amplitude: float, quality: str
) -> None:
    assert assess_reference(
        voiced_wav(duration_seconds=duration, amplitude=amplitude),
        max_bytes=8 * 1024 * 1024,
        rms_threshold=0.015,
    ).quality == quality
```

Use `tests.audio_fixtures` or extend it with a deterministic PCM WAV helper; do not record hardware audio.

- [ ] **Step 2: Write failing adapter tests**

Define the wished-for client contract:

```python
def test_voxcpm_client_sends_official_speech_shape() -> None:
    captured: dict[str, object] = {}

    def request(payload: dict[str, object]) -> bytes:
        captured.update(payload)
        return pcm_wav(sample_rate=48_000, duration_seconds=1.0)

    client = VoxCPMClient("http://tts-worker:8000", request=request)
    result = client.synthesize(
        text="(warm delivery)Hello",
        reference_wav=pcm_wav(sample_rate=16_000, duration_seconds=10.0),
    )

    assert captured["model"] == "voxcpm2"
    assert captured["input"] == "(warm delivery)Hello"
    assert captured["voice"] == "default"
    assert captured["response_format"] == "wav"
    assert str(captured["ref_audio"]).startswith("data:audio/wav;base64,")
    assert decode_wav(result, max_bytes=32 * 1024 * 1024, max_seconds=120).sample_rate == 48_000


def test_voxcpm_client_maps_oom_without_leaking_worker_message() -> None:
    client = VoxCPMClient(
        "http://tts-worker:8000",
        request=lambda _: (_ for _ in ()).throw(httpx.HTTPStatusError(
            "CUDA out of memory: private worker detail",
            request=httpx.Request("POST", "http://tts-worker:8000/v1/audio/speech"),
            response=httpx.Response(500),
        )),
    )
    with pytest.raises(PlatformError) as error:
        client.synthesize(text="hello", reference_wav=None)
    assert error.value.code == "gpu_out_of_memory"
    assert "private worker detail" not in error.value.message
```

- [ ] **Step 3: Verify RED**

Run:

```sh
python -m pytest tests/test_tts_clone.py -q
```

Expected: import failure because `agent_speak.tts_clone` does not exist.

- [ ] **Step 4: Implement focused domain types and client**

In `src/agent_speak/tts_clone.py`, define:

```python
ReferenceQuality = Literal[
    "good", "too_quiet", "too_little_voice", "too_short", "too_long"
]

@dataclass(frozen=True, slots=True)
class ReferenceAssessment:
    duration_seconds: float
    rms: float
    peak: float
    voiced_ratio: float
    quality: ReferenceQuality

STYLE_CUES = {
    "light_laugh": "speaking with a light laugh",
    "snicker": "with restrained amusement",
    "sigh": "with a soft sighing tone",
    "cough": "with a brief cough-like expression",
    "warm": "warm delivery",
    "cheerful": "cheerful tone",
    "soft": "soft voice",
    "faster": "slightly faster pace",
}
```

`assess_reference()` must inspect 20 ms frames, count frames whose RMS meets
`rms_threshold`, return `too_short` below 5 seconds, `too_long` above 30,
`too_quiet` below the threshold, `too_little_voice` below a 0.5 voiced ratio,
and `good` otherwise. Decode at most 60 seconds and enforce `max_bytes`.

`VoxCPMClient.synthesize()` must POST:

```python
{
    "model": "voxcpm2",
    "input": text,
    "voice": "default",
    "response_format": "wav",
    **({"ref_audio": f"data:audio/wav;base64,{encoded}"} if reference_wav else {}),
}
```

Use HTTPX timeouts of 2 seconds connect, 300 seconds read, 30 seconds write,
and 2 seconds pool. Read at most `max_output_bytes + 1`, validate PCM WAV,
require 48 kHz output, and map connection, timeout, OOM, non-200, and malformed
audio to stable `PlatformError` codes.

- [ ] **Step 5: Add typed settings**

Add to `Settings` and env loading:

```python
gpu_mode: Literal["asr", "tts"] = "asr"
tts_clone_worker_url: str = "http://tts-worker:8000"
voxcpm2_model_path: Path = Path("/app/models/tts/voxcpm2")
tts_clone_max_output_bytes: int = Field(default=32 * 1024 * 1024, ge=44)
tts_clone_max_output_seconds: float = Field(default=120.0, gt=0, le=300)
```

Add exact env assertions to `tests/test_contracts.py`.

- [ ] **Step 6: Verify GREEN**

Run:

```sh
python -m pytest tests/test_tts_clone.py tests/test_contracts.py -q
```

Expected: all focused tests pass.

- [ ] **Step 7: Commit**

```sh
git add src/agent_speak/tts_clone.py src/agent_speak/config.py \
  tests/test_tts_clone.py tests/test_contracts.py
git commit -m "feat: add bounded VoxCPM2 clone provider"
```

## Task 3: Add public API and localized OpenAPI contracts

**Files:**

- Create: `src/agent_speak/tts_clone_routes.py`
- Create: `tests/test_tts_clone_api.py`
- Modify: `pyproject.toml`
- Modify: `src/agent_speak/schemas.py`
- Modify: `src/agent_speak/app.py`
- Modify: `src/agent_speak/locales.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing API tests**

Build an app with an injected fake `VoxCPMClient`, then assert:

```python
@pytest.mark.anyio
async def test_clone_status_reports_wrong_mode_without_contacting_worker(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime", gpu_mode="asr"),
        tts_clone=FakeCloneClient(),
    )
    async with client_for(app) as client:
        response = await client.get("/api/v1/tts-clone/status")
    assert response.json()["state"] == "stopped"
    assert response.json()["error_code"] == "wrong_gpu_mode"
    assert response.json()["operator_hint"] == "./run.sh --tts-up"


@pytest.mark.anyio
async def test_reference_validation_never_writes_audio(tmp_path: Path) -> None:
    before = set(tmp_path.rglob("*"))
    async with clone_client(tmp_path) as client:
        response = await client.post(
            "/api/v1/tts-clone/reference/validate",
            content=voiced_wav(duration_seconds=10.0),
            headers={"content-type": "audio/wav"},
        )
    assert response.status_code == 200
    assert response.json()["quality"] == "good"
    assert set(tmp_path.rglob("*")) - before <= {
        tmp_path / "runtime" / "logs" / "gateway.jsonl"
    }


@pytest.mark.anyio
async def test_synthesis_returns_wav_without_artifact(tmp_path: Path) -> None:
    async with clone_client(tmp_path) as client:
        response = await client.post(
            "/api/v1/tts-clone/synthesize",
            data=[("text", "Hello"), ("style_cues", "warm"), ("use_clone", "true")],
            files={"reference": ("reference.wav", voiced_wav(10.0), "audio/wav")},
        )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-agent-speak-model"] == "voxcpm2"
    assert not list((tmp_path / "data").rglob("*.wav"))
```

Also test missing reference, invalid cue, invalid media type, oversized input,
worker timeout/OOM, 48 kHz output validation, query/body privacy in logs, and
all four localized OpenAPI documents.

- [ ] **Step 2: Verify RED**

Run:

```sh
python -m pytest tests/test_tts_clone_api.py -q
```

Expected: failures because the three routes and the `tts_clone` dependency
parameter do not exist.

- [ ] **Step 3: Add schemas and router**

Define these response models in `schemas.py`:

```python
class TTSCloneStatus(StrictModel):
    gpu_mode: Literal["asr", "tts"]
    accelerator: Literal["cpu", "nvidia"]
    state: Literal["stopped", "starting", "loading", "ready", "failed"]
    model: Literal["voxcpm2"]
    device: str
    ready: bool
    error_code: str | None = None
    operator_hint: str | None = None

class TTSReferenceAssessment(StrictModel):
    duration_seconds: float
    rms: float
    peak: float
    voiced_ratio: float
    quality: ReferenceQuality
```

`build_tts_clone_router()` must expose:

```python
GET  /api/v1/tts-clone/status
POST /api/v1/tts-clone/reference/validate
POST /api/v1/tts-clone/synthesize
```

The synthesis route uses `Form` and `UploadFile`, so add
`python-multipart>=0.0.20,<1` to project dependencies. Read upload chunks with
the same bounded-before-parse pattern as ASR.

- [ ] **Step 4: Wire the router and localized Swagger**

Add an optional `tts_clone` dependency to `create_app()`, instantiate
`VoxCPMClient` by default, include the router, and add all three operations to:

- `OPERATION_TAGS`
- `OPERATION_TEXT`
- `FIELD_TEXT`
- the localized tag list

Use a new `tts_clone` Swagger tag in English, Traditional Chinese, Japanese,
and Korean.

- [ ] **Step 5: Verify GREEN**

Run:

```sh
python -m pytest tests/test_tts_clone_api.py tests/test_app.py -q
```

Expected: all focused API and OpenAPI tests pass.

- [ ] **Step 6: Commit**

```sh
git add pyproject.toml src/agent_speak/schemas.py src/agent_speak/app.py \
  src/agent_speak/locales.py src/agent_speak/tts_clone_routes.py \
  tests/test_tts_clone_api.py tests/test_app.py
git commit -m "feat: expose ephemeral TTS clone API"
```

## Task 4: Add the private vLLM-Omni worker and explicit GPU modes

**Files:**

- Modify: `Dockerfile`
- Modify: `compose.yaml`
- Modify: `compose.gpu.yaml`
- Modify: `run.sh`
- Modify: `.env.example`
- Modify: `tests/test_docker_runtime.py`

- [ ] **Step 1: Write failing runtime-contract tests**

Add tests that parse Compose/Dockerfile and exercise `run.sh` with the existing
fake Docker harness:

```python
def test_tts_worker_is_private_python312_vllm_omni() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    dockerfile = (ROOT / "Dockerfile").read_text()
    worker = compose["services"]["tts-worker"]

    assert worker["profiles"] == ["tts"]
    assert worker["build"]["target"] == "tts-runtime"
    assert "ports" not in worker
    assert "devices" not in worker
    assert "/var/run/docker.sock" not in (ROOT / "compose.yaml").read_text()
    assert "FROM python:3.12-slim-bookworm AS tts-runtime" in dockerfile
    assert "vllm==0.24.0" in dockerfile
    assert "b9e9d236c3f78afd405119a5b686ebebeeb53984" in dockerfile


def test_run_script_exposes_mutually_exclusive_gpu_modes() -> None:
    script = (ROOT / "run.sh").read_text()
    assert "--asr-up" in script
    assert "--tts-up" in script
    assert "compose stop tts-worker" in script
    assert "compose stop asr-worker correction-worker" in script
    assert "/var/run/docker.sock" not in script
```

Add subprocess tests proving CPU `--tts-up` exits nonzero before Compose starts,
ASR mode starts only ASR/correction/Gateway, TTS mode starts only
TTS-worker/Gateway, status prints `gpu_mode`, and `--logs tts-worker` is valid.

- [ ] **Step 2: Verify RED**

Run:

```sh
python -m pytest tests/test_docker_runtime.py -q
```

Expected: failures for missing worker and CLI options.

- [ ] **Step 3: Add the pinned Python 3.12 worker stage**

Append to `Dockerfile`:

```dockerfile
FROM python:3.12-slim-bookworm AS tts-runtime

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/app/models/home \
    HF_HOME=/app/models/huggingface \
    XDG_CACHE_HOME=/app/models/cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install "vllm==0.24.0" --torch-backend=auto \
    && python -m pip install \
      "vllm-omni @ git+https://github.com/vllm-project/vllm-omni.git@b9e9d236c3f78afd405119a5b686ebebeeb53984"

HEALTHCHECK --interval=10s --timeout=5s --start-period=300s --retries=30 \
  CMD ["curl", "-fsS", "http://127.0.0.1:8000/health"]
```

- [ ] **Step 4: Add Compose service and remove hard Gateway worker dependencies**

Define `tts-worker` with profile `tts`, model/runtime read-only mounts where
possible, no `/dev/snd`, and no host port. Its command is:

```yaml
command:
  - vllm
  - serve
  - /app/models/tts/voxcpm2
  - --served-model-name
  - voxcpm2
  - --omni
  - --host
  - 0.0.0.0
  - --port
  - "8000"
  - --dtype
  - half
  - --gpu-memory-utilization
  - "0.85"
  - --max-num-seqs
  - "1"
  - --enforce-eager
```

Add NVIDIA runtime/device reservation in `compose.gpu.yaml`. Gateway receives
`AGENT_SPEAK_GPU_MODE` and `AGENT_SPEAK_TTS_CLONE_WORKER_URL`.
Remove the hard `depends_on` entries for ASR/correction from Gateway so it can
serve status and the inactive-mode page in either mode.

- [ ] **Step 5: Implement safe CLI switching**

Keep `--up` as an alias for ASR mode. Implement:

```bash
start_asr_mode() {
  export AGENT_SPEAK_GPU_MODE=asr
  compose --profile tts stop tts-worker
  compose up -d --force-recreate gateway asr-worker correction-worker
  wait_for_health
}

start_tts_mode() {
  if [[ "$ACCELERATOR_SELECTED" != nvidia ]]; then
    echo "ERROR: --tts-up requires a working NVIDIA Docker runtime" >&2
    return 1
  fi
  export AGENT_SPEAK_GPU_MODE=tts
  compose stop asr-worker correction-worker
  compose --profile tts up -d --build --force-recreate gateway tts-worker
  wait_for_health
}
```

Make mode transitions stop the old GPU workers before starting the new worker.
Never call `docker compose down`, so the Gateway is recreated but persistent
data remain untouched. Extend status/URLs and logs without printing secrets.

- [ ] **Step 6: Verify GREEN**

Run:

```sh
bash -n run.sh
docker compose -f compose.yaml -f compose.gpu.yaml --profile tts config --quiet
python -m pytest tests/test_docker_runtime.py -q
```

Expected: syntax, Compose, and runtime-contract tests pass.

- [ ] **Step 7: Commit**

```sh
git add Dockerfile compose.yaml compose.gpu.yaml run.sh .env.example \
  tests/test_docker_runtime.py
git commit -m "feat: add exclusive VoxCPM2 GPU mode"
```

## Task 5: Implement browser audio lifecycle test-first

**Files:**

- Create: `frontend/realtime/src/ttsClone/types.ts`
- Create: `frontend/realtime/src/ttsClone/audio.ts`
- Create: `frontend/realtime/src/ttsClone/audio.test.ts`
- Create: `frontend/realtime/src/ttsClone/api.ts`
- Create: `frontend/realtime/src/ttsClone/api.test.ts`

- [ ] **Step 1: Write failing audio lifecycle tests**

Test the wished-for interfaces with injected browser factories:

```ts
it('replaces and revokes the previous ephemeral reference', async () => {
  const revoked: string[] = [];
  const store = createEphemeralAudioStore({
    createObjectURL: (blob) => `blob:${blob.size}:${Math.random()}`,
    revokeObjectURL: (url) => revoked.push(url),
  });
  store.setReference(new Blob(['first']));
  const first = store.referenceUrl;
  store.setReference(new Blob(['second']));
  expect(revoked).toEqual([first]);
  store.dispose();
  expect(revoked).toContain(store.referenceUrl);
});

it('never starts capture until start is called', async () => {
  const getUserMedia = vi.fn();
  const recorder = createReferenceRecorder({ getUserMedia });
  expect(getUserMedia).not.toHaveBeenCalled();
  await recorder.start('mic-id');
  expect(getUserMedia).toHaveBeenCalledTimes(1);
});

it('stops automatically at thirty seconds', async () => {
  vi.useFakeTimers();
  const recorder = createReferenceRecorder(fakeBrowserAudio());
  await recorder.start('mic-id');
  await vi.advanceTimersByTimeAsync(30_000);
  expect(recorder.state).toBe('stopped');
});
```

Also test PCM16 mono WAV headers, amplitude sample bounds, explicit playback,
ended-state cleanup, and absence of autoplay.

- [ ] **Step 2: Write failing API tests**

Assert exact requests:

```ts
expect(fetch).toHaveBeenCalledWith('/api/v1/tts-clone/synthesize', {
  method: 'POST',
  body: expect.any(FormData),
});
expect(audio.play).not.toHaveBeenCalled(); // Generate never plays.
```

Test repeated `style_cues`, optional reference omission, error envelope parsing,
binary WAV response, and status polling.

- [ ] **Step 3: Verify RED**

Run:

```sh
cd frontend/realtime
npm test -- src/ttsClone/audio.test.ts src/ttsClone/api.test.ts
```

Expected: missing-module failures.

- [ ] **Step 4: Implement minimal browser modules**

`createReferenceRecorder()` must use the existing AudioWorklet/PCM conversion
approach rather than trusting browser MediaRecorder codecs. It returns:

```ts
type ReferenceRecorder = {
  state: 'idle' | 'recording' | 'stopped';
  start(deviceId: string): Promise<void>;
  stop(): Promise<Blob>;
  discard(): Promise<void>;
  subscribeAmplitude(listener: (value: number, voiced: boolean) => void): () => void;
};
```

`createEphemeralAudioStore()` owns exactly one reference and one generated
Blob URL and revokes replaced/disposed URLs. `createPlaybackAnalyser()` calls
`HTMLAudioElement.play()` only from the exported `play()` method and exposes
real analyser amplitude during playback.

- [ ] **Step 5: Verify GREEN**

Run:

```sh
cd frontend/realtime
npm test -- src/ttsClone/audio.test.ts src/ttsClone/api.test.ts
```

Expected: all new audio/API tests pass with no jsdom warnings.

- [ ] **Step 6: Commit**

```sh
git add frontend/realtime/src/ttsClone/types.ts \
  frontend/realtime/src/ttsClone/audio.ts \
  frontend/realtime/src/ttsClone/audio.test.ts \
  frontend/realtime/src/ttsClone/api.ts \
  frontend/realtime/src/ttsClone/api.test.ts
git commit -m "feat: add ephemeral browser voice audio lifecycle"
```

## Task 6: Build the two-mode TTS Clone interface

**Files:**

- Create: `frontend/realtime/src/ttsClone/App.tsx`
- Create: `frontend/realtime/src/ttsClone/App.test.tsx`
- Create: `frontend/realtime/src/ttsClone/i18n.tsx`
- Create: `frontend/realtime/src/ttsClone/i18n.test.tsx`
- Create: `frontend/realtime/src/ttsClone/components/DeviceRuntimeGate.tsx`
- Create: `frontend/realtime/src/ttsClone/components/DeviceRuntimeGate.test.tsx`
- Create: `frontend/realtime/src/ttsClone/components/VoiceOrb.tsx`
- Create: `frontend/realtime/src/ttsClone/components/VoiceOrb.test.tsx`
- Create: `frontend/realtime/src/ttsClone/components/VoiceClonePanel.tsx`
- Create: `frontend/realtime/src/ttsClone/components/TTSPlayPanel.tsx`
- Create: `frontend/realtime/src/ttsClone/styles.css`

- [ ] **Step 1: Write failing interaction tests**

Cover the approved behavior:

```tsx
it('keeps Voice Clone and TTS Play freely switchable', async () => {
  render(<App dependencies={readyDependencies()} />);
  await user.click(screen.getByRole('tab', { name: 'TTS Play' }));
  expect(screen.getByRole('tabpanel', { name: 'TTS Play' })).toBeVisible();
  await user.click(screen.getByRole('tab', { name: 'Voice Clone' }));
  expect(screen.getByRole('tabpanel', { name: 'Voice Clone' })).toBeVisible();
});

it('enables clone toggle only after a valid current reference', async () => {
  const view = render(<App dependencies={readyDependencies()} />);
  await user.click(screen.getByRole('tab', { name: 'TTS Play' }));
  expect(screen.getByRole('checkbox', { name: 'Use current cloned reference' })).toBeDisabled();
  view.rerender(<App dependencies={readyDependencies({ referenceQuality: 'good' })} />);
  expect(screen.getByRole('checkbox', { name: 'Use current cloned reference' })).toBeEnabled();
});

it('requires Generate before Play and never autoplays', async () => {
  const deps = readyDependencies();
  render(<App dependencies={deps} />);
  await user.click(screen.getByRole('tab', { name: 'TTS Play' }));
  expect(screen.getByRole('button', { name: 'Play' })).toBeDisabled();
  await user.type(screen.getByLabelText('Text to speak'), 'Hello');
  await user.click(screen.getByRole('button', { name: 'Generate' }));
  expect(deps.play).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Play' })).toBeEnabled();
});
```

Also test wrong mode (`./run.sh --tts-up` shown), CPU unavailable, model loading,
device loss, reference replacement, failed generation preserving text/reference,
all style cues, exact status live regions, keyboard tabs, and 44 px controls.

- [ ] **Step 2: Write failing Voice Orb tests**

Assert semantic state rather than pixels:

```tsx
render(<VoiceOrb state="recording" amplitude={0.8} voiced reducedMotion={false} />);
expect(screen.getByTestId('voice-orb')).toHaveAttribute('data-state', 'recording');
expect(screen.getByRole('status')).toHaveTextContent('Recording');
```

Test `idle`, `recording`, `validating`, `queued`, `generating`, `ready`,
`playing`, `complete`, `unavailable`, `error`, and reduced motion.

- [ ] **Step 3: Verify RED**

Run:

```sh
cd frontend/realtime
npm test -- src/ttsClone
```

Expected: component imports fail.

- [ ] **Step 4: Implement the approved cockpit**

Use semantic tabs and panels. The top readiness row always shows microphone,
speaker, CUDA, vLLM-Omni worker, VoxCPM2, and current-reference truth. The
central orb remains visually dominant; the runtime panel and activity timeline
remain readable but secondary.

The page reducer uses:

```ts
type CloneStudioState =
  | 'unavailable' | 'idle' | 'recording' | 'validating'
  | 'queued' | 'generating' | 'audio-ready'
  | 'playing' | 'complete' | 'error';
```

Canvas motion uses transforms/paint only, never layout. Recording amplitude
drives radius and rings; generating uses deterministic phase; playback uses the
real analyser. Reduced motion fixes geometry and changes only color/opacity.

- [ ] **Step 5: Add complete localization**

Every visible label, status, hint, cue description, error recovery action, and
ARIA string exists in `en`, `zh-TW`, `ja`, and `ko`. The catalog test compares
key sets exactly and verifies English default plus query/localStorage behavior.

- [ ] **Step 6: Run design-quality checks**

Run the UI/UX validation query:

```sh
python /home/nvidia/.codex/skills/ui-ux-pro-max/scripts/search.py \
  "voice recording playback animation accessibility loading" --domain ux
```

Then verify the implementation includes `:focus-visible`, disabled semantics,
contrast-safe text, `prefers-reduced-motion`, responsive 375/768/1024/1440
layouts, no emoji structural icons, and no layout-shifting press animation.

- [ ] **Step 7: Verify GREEN**

Run:

```sh
cd frontend/realtime
npm test -- src/ttsClone
```

Expected: all clone-studio tests pass.

- [ ] **Step 8: Commit**

```sh
git add frontend/realtime/src/ttsClone
git commit -m "feat: build VoxCPM2 clone test interface"
```

## Task 7: Build and serve the second frontend entry and homepage card

**Files:**

- Create: `frontend/realtime/tts-clone.html`
- Create: `frontend/realtime/vite.tts-clone.config.ts`
- Create: `frontend/realtime/src/ttsClone/main.tsx`
- Modify: `frontend/realtime/package.json`
- Modify: `Dockerfile`
- Modify: `src/agent_speak/app.py`
- Modify: `web/index.html`
- Modify: `web/app.css`
- Modify: `web/locale.js`
- Modify: `tests/test_webui.py`
- Modify: `tests/portal_locale.test.js`
- Generated: `web/tts_clone_test/**`

- [ ] **Step 1: Write failing route/homepage tests**

Extend `tests/test_webui.py`:

```python
@pytest.mark.anyio
async def test_tts_clone_test_route_and_home_card_are_localized(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        home = await client.get("/")
        studio = await client.get("/tts_clone_test?lang=zh-TW")
    assert 'data-route="/tts_clone_test"' in home.text
    assert "TTS Clone Test" in home.text
    assert studio.status_code == 200
    assert '<div id="root"></div>' in studio.text
```

Extend the portal locale JS test to require the TTS card description in all
four locales.

- [ ] **Step 2: Verify RED**

Run:

```sh
python -m pytest tests/test_webui.py -q
node tests/portal_locale.test.js
```

Expected: missing card/route failures.

- [ ] **Step 3: Configure and build the second Vite entry**

Add scripts:

```json
{
  "build": "tsc -b && vite build && vite build --config vite.tts-clone.config.ts",
  "build:asr": "tsc -b && vite build",
  "build:tts-clone": "tsc -b && vite build --config vite.tts-clone.config.ts"
}
```

`vite.tts-clone.config.ts` uses base `/tts_clone_test/`, input
`tts-clone.html`, and output `../../web/tts_clone_test`. Update the Docker
frontend copy to include both generated directories.

- [ ] **Step 4: Serve the page and add the localized homepage card**

Mount clone-test assets and serve `/tts_clone_test` plus trailing slash from
`app.py`. Add a fourth product card with a local SVG/Lucide-style waveform-orb
icon, index `03`, and shift System Status to `04`. Update CSS grid breakpoints
without changing the homepage's no-microphone/no-TTS behavior.

- [ ] **Step 5: Build and verify GREEN**

Run:

```sh
cd frontend/realtime
npm run build
cd ../..
python -m pytest tests/test_webui.py -q
node tests/portal_locale.test.js
```

Expected: Vite emits `web/asr_realtime` and `web/tts_clone_test`; focused tests
pass.

- [ ] **Step 6: Commit**

```sh
git add frontend/realtime/tts-clone.html \
  frontend/realtime/vite.tts-clone.config.ts \
  frontend/realtime/src/ttsClone/main.tsx frontend/realtime/package.json \
  Dockerfile src/agent_speak/app.py web/index.html web/app.css web/locale.js \
  web/tts_clone_test tests/test_webui.py tests/portal_locale.test.js
git commit -m "feat: publish localized TTS clone studio"
```

## Task 8: Complete diagnostics and operator documentation

**Files:**

- Modify: `src/agent_speak/diagnostic_logging.py`
- Modify: `src/agent_speak/tts_clone.py`
- Modify: `src/agent_speak/tts_clone_routes.py`
- Modify: `tests/test_diagnostic_logging.py`
- Modify: `tests/test_tts_clone_api.py`
- Modify: `README.md`
- Modify: `README.zh-TW.md`
- Modify: `spec/PROJECT_MAP.md`
- Modify: `spec/ARCHITECTURE.md`
- Modify: `spec/API.md`
- Modify: `spec/RUNTIME.md`
- Modify: `spec/TESTING.md`
- Modify: `spec/UI.md`
- Modify: `spec/project_herness.md`

- [ ] **Step 1: Write failing privacy-log tests**

Generate a request with identifiable text and fake audio bytes, then assert
Gateway logs contain only:

```python
assert event["event"] in {"tts.clone.started", "tts.clone.completed", "tts.clone.failed"}
assert event["stage"] == "tts"
assert event["model"] == "voxcpm2"
assert "text" not in event
assert "audio" not in event
assert "device_label" not in event
assert "exception_message" not in event
```

Also assert `./run.sh --logs tts-worker` is documented and valid.

- [ ] **Step 2: Verify RED**

Run:

```sh
python -m pytest tests/test_diagnostic_logging.py tests/test_tts_clone_api.py -q
```

Expected: missing lifecycle events.

- [ ] **Step 3: Add bounded lifecycle events**

Emit `INFO` for request start/completion, `WARNING` for recoverable
wrong-mode/timeout failures, and `ERROR` for worker/OOM failures. Allowed fields
are request ID, anonymized session, stage, model, GPU mode, worker state,
duration, output byte count, status/error code, and exception class. Add any
new field to the allowlist only if it cannot contain user content.

- [ ] **Step 4: Update all operator/spec documents**

Document:

- 40 GB preflight context without promising it remains available;
- `--models`, `--asr-up`, `--tts-up`, `--status`, and TTS logs;
- mutually exclusive GPU modes and restoration to ASR;
- zero-shot clone versus LoRA;
- ephemeral reference and generated Blob lifecycle;
- style cues as best-effort natural-language controls;
- CPU/wrong-mode behavior;
- synthetic versus real-device acceptance;
- no automatic microphone or playback.

Link the approved design and plan from `spec/PROJECT_MAP.md`.

- [ ] **Step 5: Verify GREEN and docs consistency**

Run:

```sh
python -m pytest tests/test_diagnostic_logging.py tests/test_tts_clone_api.py tests/test_docs.py -q
git diff --check
```

Expected: all focused tests and whitespace checks pass.

- [ ] **Step 6: Commit**

```sh
git add src/agent_speak/diagnostic_logging.py src/agent_speak/tts_clone.py \
  src/agent_speak/tts_clone_routes.py tests/test_diagnostic_logging.py \
  tests/test_tts_clone_api.py README.md README.zh-TW.md spec
git commit -m "docs: document VoxCPM2 clone runtime"
```

## Task 9: Full verification, model preparation, GPU smoke, and handoff

**Files:**

- Modify only if a failing verification produces a test-first fix.

- [ ] **Step 1: Run static and complete hardware-free verification**

```sh
bash -n run.sh
docker compose -f compose.yaml -f compose.gpu.yaml --profile tts config --quiet
git diff --check
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --test
```

Expected: every command exits zero; existing and new Python/React suites pass.

- [ ] **Step 2: Re-check disk before network/model work**

```sh
df -h /
docker system df
```

Expected: enough room for the 9.6 GB pinned model, temporary 15% download
overhead, TTS image layers, and the project's 8 GB reserve. If the model
preflight rejects available storage, stop and report the exact requirement;
do not weaken the reserve and do not delete unrelated user data.

- [ ] **Step 3: Download and verify all pinned models**

```sh
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --models
```

Expected:

```text
MODEL_DOWNLOAD_OK downloaded=voxcpm2
MODEL_VERIFY_OK
```

No partial target remains after success or failure.

- [ ] **Step 4: Build and start TTS mode**

```sh
AGENT_SPEAK_ACCELERATOR=nvidia ./run.sh --tts-up
AGENT_SPEAK_ACCELERATOR=nvidia ./run.sh --status
```

Expected: Gateway healthy, `gpu_mode=tts`, TTS worker/model becomes ready,
ASR/correction workers are stopped, and URLs include
`http://127.0.0.1:8765/tts_clone_test`.

- [ ] **Step 5: Run synthetic no-hardware GPU smoke**

Generate a deterministic 10-second PCM WAV in memory in a test process and
POST it to reference validation, then synthesize a short sentence with
`use_clone=true`. Validate:

- HTTP 200;
- `Content-Type: audio/wav`;
- 48 kHz PCM WAV;
- non-empty duration within the configured maximum;
- no new WAV below `data/` or `runtime/`;
- logs contain no source text or audio encoding.

Do not call browser `getUserMedia`, `arecord`, `aplay`, or physical speaker
playback during this smoke.

- [ ] **Step 6: Inspect page states without audio permission**

Use a headless browser to capture:

- homepage TTS card;
- TTS page ready state;
- Voice Clone tab before recording;
- TTS Play tab with clone disabled;
- reduced-motion state;
- 375 px and 1440 px layouts.

Expected: no console errors, horizontal overflow, clipped controls, or
microphone permission prompt.

- [ ] **Step 7: Restore the user's default ASR mode**

```sh
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --asr-up
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --status
```

Expected: Gateway/ASR/correction healthy, `gpu_mode=asr`, TTS worker stopped,
ASR device CUDA, and `/asr_realtime` remains operational.

- [ ] **Step 8: Final repository audit**

```sh
git status -sb
git diff --check
git ls-files | rg '(^|/)(models|runtime|data|logs)(/|$)|\.wav$|\.env$'
```

Expected: no private/model/runtime files tracked, `.superpowers/` remains
untracked, and only intentional source/docs/generated frontend assets remain.

The final handoff reports:

- `/tts_clone_test` URL;
- active mode restored to ASR;
- exact test counts;
- synthetic GPU smoke result;
- that real microphone/physical playback still require the user's own Record
  and Play clicks;
- commit hashes;
- whether anything remains uncommitted or unpushed.
