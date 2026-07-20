# NVIDIA GPU Auto-Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically run Agent Speak with NVIDIA CUDA acceleration when the host and Docker support it, while preserving deterministic CPU fallback and unchanged `/api/v1` contracts.

**Architecture:** Keep `compose.yaml` CPU-safe and add a GPU-only Compose override that builds a distinct image variant with CUDA 12 libraries. `run.sh` performs side-effect-free host preflight, constructs one shared Compose command array for every lifecycle action, and passes the original `auto|cpu|nvidia` request into the container. A pure Python selector probes CUDA inside the container, while `FasterWhisperASR` and `/api/v1/capabilities` report the device actually selected.

**Tech Stack:** Bash, Docker Compose v2, Python 3.11, Pydantic, FastAPI, Faster-Whisper/CTranslate2, CUDA 12, cuDNN 9, pytest.

---

## File Map

- Create `src/agent_speak/accelerators.py`: pure accelerator-mode validation and in-container CUDA selection.
- Create `tests/test_accelerators.py`: deterministic CUDA probe, fallback, and strict-mode tests.
- Modify `src/agent_speak/config.py`: typed `AGENT_SPEAK_ACCELERATOR` and GPU compute-type settings.
- Modify `src/agent_speak/production.py`: initialize Faster-Whisper with the selected device and compute type.
- Modify `src/agent_speak/pipeline.py`: wire settings into ASR and expose actual device capabilities.
- Modify `tests/test_production_providers.py`: provider factory arguments, fallback, strict failure, and capability truth.
- Modify `pyproject.toml`: optional CUDA 12/cuDNN 9 runtime dependencies for the GPU image variant.
- Modify `Dockerfile`: build distinct CPU and NVIDIA variants without maintaining duplicated Dockerfiles.
- Create `compose.gpu.yaml`: GPU reservation and GPU image/build arguments for the Gateway only.
- Modify `compose.yaml`: pass accelerator settings into the Gateway while leaving `gateway-test` CPU-only.
- Modify `tests/test_docker_runtime.py`: Compose security, image variant, host detection, fallback, and lifecycle routing tests.
- Modify `run.sh`: accelerator preflight, shared Compose command routing, strict/auto behavior, and status reporting.
- Modify `.env.example`, `README.md`, `README.zh-TW.md`, `spec/RUNTIME.md`, and `spec/TESTING.md`: operator modes, prerequisites, status fields, and verification.

### Task 1: Pure Accelerator Selection and Settings

**Files:**
- Create: `src/agent_speak/accelerators.py`
- Create: `tests/test_accelerators.py`
- Modify: `src/agent_speak/config.py`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Write failing selector and settings tests**

Create `tests/test_accelerators.py` with focused cases that inject the probe instead of touching real GPU hardware:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_speak.accelerators import ASRDeviceSelection, select_asr_device
from agent_speak.config import Settings
from agent_speak.errors import PlatformError


def test_cpu_mode_skips_cuda_probe() -> None:
    called = False

    def probe() -> bool:
        nonlocal called
        called = True
        return True

    selected = select_asr_device("cpu", "int8", "float16", probe)

    assert selected == ASRDeviceSelection("cpu", "int8", None)
    assert called is False


def test_auto_uses_cuda_when_probe_succeeds() -> None:
    selected = select_asr_device("auto", "int8", "float16", lambda: True)
    assert selected == ASRDeviceSelection("cuda", "float16", None)


def test_auto_falls_back_once_when_probe_fails() -> None:
    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        raise RuntimeError("libcudnn unavailable")

    selected = select_asr_device("auto", "int8", "float16", probe)

    assert selected.device == "cpu"
    assert selected.compute_type == "int8"
    assert selected.fallback_reason == "CUDA probe failed"
    assert calls == 1


def test_nvidia_mode_rejects_failed_cuda_probe() -> None:
    with pytest.raises(PlatformError, match="NVIDIA acceleration was required") as captured:
        select_asr_device("nvidia", "int8", "float16", lambda: False)
    assert captured.value.code == "provider_unavailable"
    assert captured.value.stage == "asr"


def test_settings_validate_accelerator_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_SPEAK_ACCELERATOR", "nvidia")
    monkeypatch.setenv("AGENT_SPEAK_ASR_CUDA_COMPUTE_TYPE", "float16")
    settings = Settings.from_env()
    assert settings.accelerator == "nvidia"
    assert settings.asr_cuda_compute_type == "float16"

    monkeypatch.setenv("AGENT_SPEAK_ACCELERATOR", "rocm")
    with pytest.raises(ValidationError):
        Settings.from_env()
```

- [ ] **Step 2: Run the tests and verify the expected import/config failures**

Run:

```bash
python -m pytest tests/test_accelerators.py tests/test_contracts.py -q
```

Expected: FAIL because `agent_speak.accelerators` and the new Settings fields do not exist.

- [ ] **Step 3: Implement the selector and typed settings**

Create `src/agent_speak/accelerators.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from .errors import PlatformError

AcceleratorMode = Literal["auto", "cpu", "nvidia"]


@dataclass(frozen=True, slots=True)
class ASRDeviceSelection:
    device: Literal["cpu", "cuda"]
    compute_type: str
    fallback_reason: str | None


def ctranslate2_cuda_available() -> bool:
    import ctranslate2

    if ctranslate2.get_cuda_device_count() < 1:
        return False
    return bool(ctranslate2.get_supported_compute_types("cuda"))


def select_asr_device(
    mode: AcceleratorMode,
    cpu_compute_type: str,
    cuda_compute_type: str,
    cuda_probe: Callable[[], bool] = ctranslate2_cuda_available,
) -> ASRDeviceSelection:
    if mode == "cpu":
        return ASRDeviceSelection("cpu", cpu_compute_type, None)
    try:
        available = cuda_probe()
    except Exception as exc:
        if mode == "nvidia":
            raise PlatformError(
                "provider_unavailable",
                "NVIDIA acceleration was required but the CUDA probe failed",
                status_code=503,
                stage="asr",
                retryable=False,
            ) from exc
        return ASRDeviceSelection("cpu", cpu_compute_type, "CUDA probe failed")
    if available:
        return ASRDeviceSelection("cuda", cuda_compute_type, None)
    if mode == "nvidia":
        raise PlatformError(
            "provider_unavailable",
            "NVIDIA acceleration was required but CUDA is unavailable",
            status_code=503,
            stage="asr",
            retryable=False,
        )
    return ASRDeviceSelection("cpu", cpu_compute_type, "CUDA is unavailable inside the container")
```

Add to `Settings` in `src/agent_speak/config.py`:

```python
from typing import Any, Literal

# Inside Settings
accelerator: Literal["auto", "cpu", "nvidia"] = "auto"
asr_compute_type: str = "int8"
asr_cuda_compute_type: str = "float16"
```

Keep the generic `from_env` loader unchanged so both fields use the existing `AGENT_SPEAK_*` mapping.

- [ ] **Step 4: Run selector and configuration tests**

Run:

```bash
python -m pytest tests/test_accelerators.py tests/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the pure selection boundary**

```bash
git add src/agent_speak/accelerators.py src/agent_speak/config.py tests/test_accelerators.py tests/test_contracts.py
git commit -m "feat: select ASR accelerator deterministically"
```

### Task 2: Faster-Whisper Device Wiring and Capability Truth

**Files:**
- Modify: `src/agent_speak/production.py`
- Modify: `src/agent_speak/pipeline.py`
- Modify: `tests/test_production_providers.py`

- [ ] **Step 1: Add failing provider device tests**

Extend `tests/test_production_providers.py` with a factory that captures initialization arguments:

```python
class CapturingWhisperFactory:
    def __init__(self, model: FakeWhisperModel) -> None:
        self.model = model
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, model_name: str, **kwargs: object) -> FakeWhisperModel:
        self.calls.append((model_name, kwargs))
        return self.model


def test_faster_whisper_uses_selected_cuda_device_and_compute_type() -> None:
    model = FakeWhisperModel()
    factory = CapturingWhisperFactory(model)
    provider = FasterWhisperASR(
        model_name="small",
        language="zh",
        accelerator="auto",
        cpu_compute_type="int8",
        cuda_compute_type="float16",
        cuda_probe=lambda: True,
        model_factory=factory,
    )

    provider.transcribe(wav_bytes())

    assert provider.device == "cuda"
    assert provider.fallback_reason is None
    assert factory.calls[0][1]["device"] == "cuda"
    assert factory.calls[0][1]["compute_type"] == "float16"


def test_faster_whisper_auto_reports_cpu_fallback() -> None:
    provider = FasterWhisperASR(
        accelerator="auto",
        cpu_compute_type="int8",
        cuda_compute_type="float16",
        cuda_probe=lambda: False,
        model_factory=lambda *args, **kwargs: FakeWhisperModel(),
    )
    assert provider.device == "cpu"
    assert provider.fallback_reason == "CUDA is unavailable inside the container"


def test_configured_capability_reports_actual_asr_device(tmp_path: Path) -> None:
    settings = Settings(accelerator="cpu", tts_model_path=tmp_path / "voice.onnx")
    providers = ProviderSet.configured(settings, vad=object())
    capability = {item.stage: item for item in providers.capabilities()}["asr"]
    assert capability.device == "cpu"
    assert "CPU inference" in capability.limitations[0]
```

Update the existing provider construction test to use `cpu_compute_type="int8"` rather than the removed `compute_type` argument.

- [ ] **Step 2: Run the provider tests and verify they fail**

Run:

```bash
python -m pytest tests/test_production_providers.py -q
```

Expected: FAIL because `FasterWhisperASR` does not accept accelerator settings and has no `device` property.

- [ ] **Step 3: Wire selection into the production ASR provider**

In `src/agent_speak/production.py`, update `FasterWhisperASR.__init__` and model creation:

```python
from .accelerators import AcceleratorMode, select_asr_device


def __init__(
    self,
    *,
    model_name: str = "small",
    language: str | None = "zh",
    accelerator: AcceleratorMode = "auto",
    cpu_compute_type: str = "int8",
    cuda_compute_type: str = "float16",
    cpu_threads: int = 4,
    cuda_probe: Callable[[], bool] | None = None,
    model_factory: Callable[..., Any] | None = None,
) -> None:
    self.model_name = model_name
    self.language = language
    self.cpu_threads = cpu_threads
    selection = select_asr_device(
        accelerator,
        cpu_compute_type,
        cuda_compute_type,
        cuda_probe or ctranslate2_cuda_available,
    )
    self.device = selection.device
    self.compute_type = selection.compute_type
    self.fallback_reason = selection.fallback_reason
    self._model_factory = model_factory
    self._local_model_resolver = self._resolve_local_model
    self._model = None
    self._lock = Lock()
```

Import `ctranslate2_cuda_available` with `AcceleratorMode`. Replace the hard-coded model factory arguments with:

```python
self._model = factory(
    self.model_name,
    device=self.device,
    compute_type=self.compute_type,
    cpu_threads=self.cpu_threads,
    num_workers=1,
)
```

Do not catch model corruption or transcription failures as accelerator fallback. Selection happens once during provider construction; later failures continue through the existing stable error envelopes.

- [ ] **Step 4: Wire settings and actual device into capabilities**

In `ProviderSet.configured` in `src/agent_speak/pipeline.py`, construct ASR with:

```python
asr = FasterWhisperASR(
    model_name=settings.asr_model,
    language=settings.asr_language,
    accelerator=settings.accelerator,
    cpu_compute_type=settings.asr_compute_type,
    cuda_compute_type=settings.asr_cuda_compute_type,
    cpu_threads=settings.asr_cpu_threads,
)
```

Build the ASR limitation without changing the schema:

```python
device_label = "CUDA inference." if asr.device == "cuda" else "CPU inference."
asr_limitations = [f"Faster-Whisper local transcription; {device_label}"]
if asr.fallback_reason:
    asr_limitations.append(f"Automatic CPU fallback: {asr.fallback_reason}")
```

Pass `device=asr.device` into the ASR `ProviderCapability`; keep the existing missing-model limitation when `asr_ready` is false.

- [ ] **Step 5: Run provider and API capability tests**

Run:

```bash
python -m pytest tests/test_production_providers.py tests/test_app.py tests/test_webui.py -q
```

Expected: PASS, including unchanged `/api/v1/capabilities` response shape.

- [ ] **Step 6: Commit provider integration**

```bash
git add src/agent_speak/production.py src/agent_speak/pipeline.py tests/test_production_providers.py
git commit -m "feat: run Faster-Whisper on selected device"
```

### Task 3: CPU-Safe Compose with an NVIDIA Image Variant

**Files:**
- Modify: `pyproject.toml`
- Modify: `Dockerfile`
- Modify: `compose.yaml`
- Create: `compose.gpu.yaml`
- Modify: `tests/test_docker_runtime.py`

- [ ] **Step 1: Write failing Compose and image-boundary tests**

Add this test to `tests/test_docker_runtime.py`:

```python
def test_gpu_override_is_nvidia_only_and_keeps_test_service_hermetic() -> None:
    base = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    gpu = yaml.safe_load((ROOT / "compose.gpu.yaml").read_text(encoding="utf-8"))
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    gateway = gpu["services"]["gateway"]
    devices = gateway["deploy"]["resources"]["reservations"]["devices"]
    assert devices == [{"driver": "nvidia", "count": "all", "capabilities": ["gpu"]}]
    assert gateway["image"] == "agent-speak:gpu-local"
    assert gateway["build"]["args"]["AGENT_SPEAK_IMAGE_VARIANT"] == "nvidia"
    assert "privileged" not in gateway
    assert "devices" not in gateway
    assert "gateway-test" not in gpu["services"]

    assert base["services"]["gateway"]["environment"]["AGENT_SPEAK_ACCELERATOR"] == "${AGENT_SPEAK_ACCELERATOR:-auto}"
    assert "AGENT_SPEAK_IMAGE_VARIANT" in dockerfile
    assert "nvidia-cublas-cu12" in pyproject
    assert "nvidia-cudnn-cu12" in pyproject
```

- [ ] **Step 2: Run the test and verify the missing override failure**

Run:

```bash
python -m pytest tests/test_docker_runtime.py::test_gpu_override_is_nvidia_only_and_keeps_test_service_hermetic -q
```

Expected: FAIL because `compose.gpu.yaml` does not exist.

- [ ] **Step 3: Add pinned GPU optional dependencies and image variant**

Add to `[project.optional-dependencies]` in `pyproject.toml`:

```toml
gpu = [
  "nvidia-cublas-cu12>=12,<13",
  "nvidia-cudnn-cu12>=9,<10",
]
```

In `Dockerfile`, declare the variant before dependency installation and conditionally install extras:

```dockerfile
ARG AGENT_SPEAK_IMAGE_VARIANT=cpu

RUN python -m pip install --upgrade pip setuptools wheel \
    && if [ "$AGENT_SPEAK_IMAGE_VARIANT" = "nvidia" ]; then \
         python -m pip install -e '.[test,gpu]'; \
       else \
         python -m pip install -e '.[test]'; \
       fi

ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib
```

Keep the default `cpu` so the existing image remains portable. The GPU Compose build uses a distinct image tag, preventing a CPU build from overwriting the GPU image or vice versa.

- [ ] **Step 4: Add the GPU override and pass settings through base Compose**

Create `compose.gpu.yaml`:

```yaml
services:
  gateway:
    build:
      args:
        AGENT_SPEAK_IMAGE_VARIANT: nvidia
    image: agent-speak:gpu-local
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

Add these environment values to the base Gateway in `compose.yaml`:

```yaml
AGENT_SPEAK_ACCELERATOR: "${AGENT_SPEAK_ACCELERATOR:-auto}"
AGENT_SPEAK_ASR_CUDA_COMPUTE_TYPE: "${AGENT_SPEAK_ASR_CUDA_COMPUTE_TYPE:-float16}"
```

Do not add them to `gateway-test`; its existing no-network/no-device boundary remains unchanged.

- [ ] **Step 5: Validate static Compose security and merged configuration**

Run:

```bash
python -m pytest tests/test_docker_runtime.py::test_gpu_override_is_nvidia_only_and_keeps_test_service_hermetic -q
docker compose -f compose.yaml -f compose.gpu.yaml config >/tmp/agent-speak-gpu-compose.yaml
```

Expected: test PASS and Compose config exits 0. Inspect the generated config only for the Gateway GPU reservation; do not commit `/tmp/agent-speak-gpu-compose.yaml`.

- [ ] **Step 6: Commit the GPU image and Compose boundary**

```bash
git add pyproject.toml Dockerfile compose.yaml compose.gpu.yaml tests/test_docker_runtime.py
git commit -m "feat: add isolated NVIDIA container variant"
```

### Task 4: Host Preflight and Shared Compose Routing

**Files:**
- Modify: `run.sh`
- Modify: `tests/test_docker_runtime.py`

- [ ] **Step 1: Add reusable fake-host test helpers and failing mode tests**

Add helpers to `tests/test_docker_runtime.py` that create both `docker` and `nvidia-smi` fakes:

```python
def _accelerator_env(tmp_path: Path, *, gpu: bool, runtime: bool) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "docker.log"
    docker = fake_bin / "docker"
    runtimes = '{"io.containerd.runc.v2":{},"nvidia":{}}' if runtime else '{"runc":{}}'
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n"
        "if [[ \"$*\" == 'compose config --environment' ]]; then exit 0; fi\n"
        "if [[ \"$*\" == 'info --format {{json .Runtimes}}' ]]; then "
        f"printf '%s\\n' '{runtimes}'; exit 0; fi\n"
        "if [[ \"$1 $2\" == 'compose ps' ]]; then echo fake-container; fi\n"
        "if [[ \"$1\" == inspect ]]; then echo healthy; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    nvidia_smi = fake_bin / "nvidia-smi"
    nvidia_smi.write_text(
        "#!/usr/bin/env bash\n" + ("echo 'GPU 0: Fake NVIDIA GPU'; exit 0\n" if gpu else "exit 1\n"),
        encoding="utf-8",
    )
    nvidia_smi.chmod(0o755)
    env = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_DOCKER_LOG": str(log),
        "AGENT_SPEAK_ACCELERATOR": "auto",
    }
    return env, log
```

Add these cases:

```python
def test_auto_mode_routes_every_command_through_gpu_override(tmp_path: Path) -> None:
    env, log = _accelerator_env(tmp_path, gpu=True, runtime=True)
    result = subprocess.run([str(ROOT / "run.sh"), "--up"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    calls = log.read_text(encoding="utf-8")
    assert "compose -f compose.yaml -f compose.gpu.yaml up -d" in calls
    assert "ACCELERATOR_SELECTED mode=nvidia" in result.stdout


def test_auto_mode_falls_back_to_cpu_when_runtime_is_missing(tmp_path: Path) -> None:
    env, log = _accelerator_env(tmp_path, gpu=True, runtime=False)
    result = subprocess.run([str(ROOT / "run.sh"), "--up"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    calls = log.read_text(encoding="utf-8")
    assert "compose -f compose.yaml up -d" in calls
    assert "compose.gpu.yaml" not in calls
    assert "NVIDIA Docker runtime is unavailable" in result.stderr


def test_cpu_mode_never_calls_nvidia_smi(tmp_path: Path) -> None:
    env, log = _accelerator_env(tmp_path, gpu=True, runtime=True)
    env["AGENT_SPEAK_ACCELERATOR"] = "cpu"
    result = subprocess.run([str(ROOT / "run.sh"), "--down"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "compose.gpu.yaml" not in log.read_text(encoding="utf-8")


def test_strict_nvidia_mode_fails_before_compose_start(tmp_path: Path) -> None:
    env, log = _accelerator_env(tmp_path, gpu=False, runtime=True)
    env["AGENT_SPEAK_ACCELERATOR"] = "nvidia"
    result = subprocess.run([str(ROOT / "run.sh"), "--up"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "NVIDIA acceleration is required" in result.stderr
    assert " up -d" not in log.read_text(encoding="utf-8")


def test_invalid_accelerator_mode_fails_before_compose_start(tmp_path: Path) -> None:
    env, log = _accelerator_env(tmp_path, gpu=True, runtime=True)
    env["AGENT_SPEAK_ACCELERATOR"] = "rocm"
    result = subprocess.run([str(ROOT / "run.sh"), "--up"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert "AGENT_SPEAK_ACCELERATOR must be auto, cpu, or nvidia" in result.stderr
    assert " up -d" not in log.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the new run-script tests and verify CPU-only behavior fails expectations**

Run:

```bash
python -m pytest tests/test_docker_runtime.py -k 'accelerator or gpu_override or auto_mode or cpu_mode or strict_nvidia' -q
```

Expected: FAIL because `run.sh` does not detect accelerators or route Compose through an array.

- [ ] **Step 3: Import the new environment keys safely**

Extend the strict whitelist in `load_compose_environment`:

```bash
AGENT_SPEAK_AUDIO_GID|AGENT_SPEAK_ACCELERATOR|AGENT_SPEAK_ASR_CUDA_COMPUTE_TYPE)
```

Do not source `.env`; explicit process environment must continue to win.

- [ ] **Step 4: Implement accelerator selection and one Compose wrapper**

Add global state after `ROOT_DIR`:

```bash
COMPOSE=(docker compose -f compose.yaml)
ACCELERATOR_SELECTED=cpu
ACCELERATOR_REASON="forced CPU"
```

Add these functions after `load_compose_environment`:

```bash
compose() {
  "${COMPOSE[@]}" "$@"
}

configure_accelerator() {
  local requested=${AGENT_SPEAK_ACCELERATOR:-auto}
  local failure=""
  case "$requested" in
    cpu)
      ACCELERATOR_SELECTED=cpu
      ACCELERATOR_REASON="forced CPU"
      ;;
    auto|nvidia)
      if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi -L >/dev/null 2>&1; then
        failure="NVIDIA GPU or driver is unavailable"
      elif ! docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'; then
        failure="NVIDIA Docker runtime is unavailable"
      fi
      if [[ -z "$failure" ]]; then
        COMPOSE+=( -f compose.gpu.yaml )
        ACCELERATOR_SELECTED=nvidia
        ACCELERATOR_REASON="NVIDIA preflight passed"
      elif [[ "$requested" == nvidia ]]; then
        echo "ERROR: NVIDIA acceleration is required: $failure" >&2
        return 1
      else
        ACCELERATOR_SELECTED=cpu
        ACCELERATOR_REASON="$failure"
        echo "WARNING: $failure; falling back to CPU." >&2
      fi
      ;;
    *)
      echo "ERROR: AGENT_SPEAK_ACCELERATOR must be auto, cpu, or nvidia (got: $requested)" >&2
      return 2
      ;;
  esac
  export AGENT_SPEAK_ACCELERATOR=$requested
  echo "ACCELERATOR_SELECTED mode=$ACCELERATOR_SELECTED reason=$ACCELERATOR_REASON"
}
```

Call `configure_accelerator` after `load_compose_environment` and before `prepare_runtime`, using this status-preserving form (a negated `if !` would lose the original status):

```bash
set +e
configure_accelerator
accelerator_status=$?
set -e
if (( accelerator_status != 0 )); then
  exit "$accelerator_status"
fi
```

Replace every operational `docker compose ...` call in `load_compose_environment`, `wait_for_health`, and the `case` branches with `compose ...`. Keep `require_docker` using `docker compose version`, because selection has not happened yet.

- [ ] **Step 5: Update existing fake-Docker assertions for explicit base Compose files**

Existing tests currently match fragments such as `compose up -d`. Update them to accept the new prefix and assert the same file list is used by `build`, `up`, `down`, `status`, `logs`, and `test`:

```python
assert "compose -f compose.yaml" in calls
```

Keep path preparation and hermetic `gateway-test` assertions intact.

- [ ] **Step 6: Run all Docker runtime unit tests**

Run:

```bash
python -m pytest tests/test_docker_runtime.py -q
bash -n run.sh
```

Expected: PASS and no shell syntax errors.

- [ ] **Step 7: Commit host detection and routing**

```bash
git add run.sh tests/test_docker_runtime.py
git commit -m "feat: auto-select NVIDIA Compose runtime"
```

### Task 5: Status Truth, Documentation, and End-to-End Verification

**Files:**
- Modify: `run.sh`
- Modify: `tests/test_docker_runtime.py`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `README.zh-TW.md`
- Modify: `spec/RUNTIME.md`
- Modify: `spec/TESTING.md`

- [ ] **Step 1: Write a failing status-output test**

Extend the status fake in `tests/test_docker_runtime.py` so `compose exec -T gateway python -c ...` returns `cuda`, then assert:

```python
def test_status_reports_host_selection_and_actual_provider_device(tmp_path: Path) -> None:
    env, _ = _accelerator_env(tmp_path, gpu=True, runtime=True)
    env["FAKE_ASR_DEVICE"] = "cuda"
    result = subprocess.run([str(ROOT / "run.sh"), "--status"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "accelerator=nvidia" in result.stdout
    assert "asr_device=cuda" in result.stdout
```

In the fake Docker script, handle the capability probe before the generic exit:

```bash
if [[ "$*" == *"providers"* && "$*" == *"/api/v1/capabilities"* ]]; then
  echo "${FAKE_ASR_DEVICE:-unknown}"
  exit 0
fi
```

- [ ] **Step 2: Run the status test and verify the missing fields**

Run:

```bash
python -m pytest tests/test_docker_runtime.py::test_status_reports_host_selection_and_actual_provider_device -q
```

Expected: FAIL because `--status` does not query provider capabilities or print accelerator fields.

- [ ] **Step 3: Add the bounded capability probe to `--status`**

In the `--status` branch, default to `unknown` and query only the ASR device:

```bash
asr_device=$(compose exec -T gateway python -c '
import json
import urllib.request
payload = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/v1/capabilities", timeout=3))
print(next(item["device"] for item in payload["providers"] if item["stage"] == "asr"))
' 2>/dev/null || printf 'unknown')
```

Append `accelerator=$ACCELERATOR_SELECTED asr_device=$asr_device` to the existing single `STATUS_*` line. Do not print UUIDs, full driver output, environment contents, or error stack traces.

- [ ] **Step 4: Document modes and safe fallback**

Add to `.env.example`:

```dotenv
# auto uses NVIDIA only when both the driver and Docker runtime are ready.
# cpu forces the portable image; nvidia fails rather than silently falling back.
AGENT_SPEAK_ACCELERATOR=auto
AGENT_SPEAK_ASR_CUDA_COMPUTE_TYPE=float16
```

Update both READMEs and `spec/RUNTIME.md` with:

- NVIDIA acceleration is optional; CPU remains the portable default path.
- `auto|cpu|nvidia` semantics.
- NVIDIA Container Toolkit is required for GPU mode.
- GPU mode builds the separate `agent-speak:gpu-local` variant containing CUDA 12/cuDNN 9 libraries.
- `--status` reports selected accelerator and actual ASR device.

Use this operator wording in the English README and runtime spec:

```markdown
`AGENT_SPEAK_ACCELERATOR=auto` is the default. It selects the separate NVIDIA image only when `nvidia-smi` and Docker's NVIDIA runtime are both ready; otherwise it prints the reason and starts the CPU image. Use `cpu` to force the portable CPU/INT8 path or `nvidia` to require CUDA and fail instead of falling back. NVIDIA mode requires the NVIDIA Container Toolkit and builds `agent-speak:gpu-local` with CUDA 12 and cuDNN 9. `./run.sh --status` reports both the selected Compose accelerator and the ASR provider's actual device.
```

Use this equivalent text in the Traditional Chinese README:

```markdown
`AGENT_SPEAK_ACCELERATOR=auto` 是預設值。只有在 `nvidia-smi` 與 Docker NVIDIA runtime 都可用時才選擇獨立 NVIDIA 映像；否則會顯示原因並啟動 CPU 映像。`cpu` 會強制使用可攜式 CPU/INT8 路徑；`nvidia` 則要求 CUDA，無法使用時直接失敗而不降級。NVIDIA 模式需要 NVIDIA Container Toolkit，並建置含 CUDA 12 與 cuDNN 9 的 `agent-speak:gpu-local`。`./run.sh --status` 會同時顯示 Compose 選擇的 accelerator 與 ASR Provider 實際使用的 device。
```

Update `spec/TESTING.md` to distinguish hermetic CPU tests from host GPU verification. Include these exact commands:

```bash
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --build
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --rebuild
./run.sh --status
docker compose -f compose.yaml -f compose.gpu.yaml exec -T gateway nvidia-smi -L
```

- [ ] **Step 5: Run focused tests and the repository-required full test suite before rebuilding**

Run:

```bash
python -m pytest tests/test_accelerators.py tests/test_production_providers.py tests/test_docker_runtime.py tests/test_app.py -q
./run.sh --test
```

Expected: all pytest tests PASS and `TESTS_OK`. The test container must remain CPU-only, without `/dev/snd`, production mounts, network, or GPU reservation.

- [ ] **Step 6: Commit status and documentation**

```bash
git add run.sh tests/test_docker_runtime.py .env.example README.md README.zh-TW.md spec/RUNTIME.md spec/TESTING.md
git commit -m "docs: explain automatic GPU acceleration"
```

- [ ] **Step 7: Verify forced CPU on the real host**

Run:

```bash
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --down_up
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --status
```

Expected: Gateway healthy, `accelerator=cpu`, `asr_device=cpu`, and existing capture/playback reporting remains present.

- [ ] **Step 8: Verify automatic NVIDIA selection on the real host**

Run:

```bash
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --rebuild
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --status
docker compose -f compose.yaml -f compose.gpu.yaml exec -T gateway nvidia-smi -L
```

Expected: GPU image builds, Gateway becomes healthy, status reports `accelerator=nvidia asr_device=cuda`, and the container lists at least one NVIDIA GPU. The build may download large CUDA packages and therefore requires network access.

- [ ] **Step 9: Exercise one bounded ASR request without microphone capture**

Generate speech through the existing Piper API without playback, then send that bounded WAV to ASR from inside the GPU Gateway:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml exec -T gateway python -c '
import json
import urllib.request
base = "http://127.0.0.1:8765/api/v1"
tts = urllib.request.Request(
    base + "/tts/synthesize",
    data=json.dumps({"text": "這是一段 GPU 語音辨識測試。"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
audio_url = json.load(urllib.request.urlopen(tts, timeout=30))["audio_url"]
audio = urllib.request.urlopen("http://127.0.0.1:8765" + audio_url, timeout=30).read()
asr = urllib.request.Request(
    base + "/audio/asr",
    data=audio,
    headers={"Content-Type": "audio/wav"},
    method="POST",
)
print(json.load(urllib.request.urlopen(asr, timeout=60)))
'
```

Expected: ASR returns a normal transcript, capabilities still report `device=cuda`, and Gateway logs contain no CUDA library error. Do not commit the WAV or logs.

- [ ] **Step 10: Run final verification and inspect repository scope**

Run:

```bash
./run.sh --test
./run.sh --status
git diff --check
git status --short
```

Expected: `TESTS_OK`, healthy status, no whitespace errors, and only the pre-existing untracked `.superpowers/` remains outside committed work.
