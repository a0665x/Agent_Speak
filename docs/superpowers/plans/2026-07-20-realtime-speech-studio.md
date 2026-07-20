# Realtime Speech Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/realtime` React application that continuously streams explicitly authorized microphone audio through realtime VAD, adaptive endpoint detection, rolling/final Faster-Whisper ASR, local Qwen correction, and ordered transcript updates without invoking an Agent or speaker.

**Architecture:** Keep FastAPI as the session, WebSocket, VAD, endpoint, and bounded-scheduler owner. Move production ASR into an internal Agent Speak worker and use an internal llama.cpp service for endpoint/correction inference; keep all existing public REST and MCP contracts intact. Build a separate React/TypeScript/Vite application whose AudioWorklet sends bounded PCM16 frames and whose UI reconciles ordered utterance events.

**Tech Stack:** Python 3.11, FastAPI, asyncio, Pydantic, Silero VAD ONNX, Faster-Whisper/CTranslate2, llama.cpp, Qwen2.5-1.5B-Instruct Q4_K_M, React 19, TypeScript, Vite, Vitest, Testing Library, AudioWorklet, WebSocket, React Bits `Waves`, Docker Compose, pytest.

---

## Preconditions and execution rules

- Work directly on `main`, as explicitly requested by the user.
- Before behavior changes, run `./run.sh --status` and `./run.sh --test`.
- Do not open the microphone, play sound, or run hardware browser tests without fresh explicit user consent.
- Preserve `/api/v1`, the provider boundaries, `/`, `/codex`, and the MCP data/control-plane split.
- Never commit `.env`, credentials, recordings, PCM/WAV files, voice features, databases, runtime data, model weights, caches, logs, or `.superpowers/`.
- Every behavior change starts with a failing test, then the minimum implementation, then focused and full regression tests.
- Source design: `docs/superpowers/specs/2026-07-20-realtime-speech-studio-design.md`.

## File structure

### Backend files to create

- `src/agent_speak/realtime_models.py` — strict realtime control/event/job/result models.
- `src/agent_speak/realtime_audio.py` — PCM validation, WAV wrapping, signal level, and frame VAD adapters.
- `src/agent_speak/realtime_endpoint.py` — deterministic streaming utterance/endpoint state machine.
- `src/agent_speak/realtime_queue.py` — bounded final/partial ASR and endpoint/correction schedulers.
- `src/agent_speak/transcripts.py` — stable-prefix and one-sentence revision ledger.
- `src/agent_speak/text_inference.py` — llama.cpp endpoint/correction client, prompts, JSON validation, and edit guard.
- `src/agent_speak/asr_worker.py` — internal Faster-Whisper worker FastAPI application.
- `src/agent_speak/remote_asr.py` — public provider-compatible client for the internal ASR worker.
- `src/agent_speak/realtime.py` — realtime stream/coordinator lifecycle and worker loops.
- `src/agent_speak/realtime_routes.py` — `/api/v1/realtime/sessions/{id}` WebSocket transport.
- `scripts/bootstrap_models.py` — idempotent ignored-model bootstrap for Faster-Whisper and Qwen GGUF.
- `scripts/realtime_smoke.py` — synthetic in-memory WebSocket acceptance without audio hardware.

### Backend files to modify

- `src/agent_speak/config.py` — validated realtime and internal-worker settings.
- `src/agent_speak/providers.py` — revision provider protocol.
- `src/agent_speak/production.py` — explicit Faster-Whisper warmup method.
- `src/agent_speak/pipeline.py` — select local versus internal HTTP providers without changing REST contracts.
- `src/agent_speak/schemas.py` — report worker/device readiness without changing existing fields.
- `src/agent_speak/app.py` — initialize realtime coordinator, register transport, and serve Vite output.
- `pyproject.toml` — runtime dependencies for HTTP clients and Silero ONNX.

### Frontend files to create

- `frontend/realtime/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `index.html` — isolated Vite application and reproducible dependency graph.
- `frontend/realtime/public/pcm-capture.worklet.js` — PCM16 frame conversion off the main thread.
- `frontend/realtime/src/main.tsx`, `App.tsx`, `styles.css` — application entry, layout, and design tokens.
- `frontend/realtime/src/types.ts` — control and event discriminated unions.
- `frontend/realtime/src/state/reducer.ts` — sequence/utterance-safe UI reducer.
- `frontend/realtime/src/audio/deviceGate.ts` — explicit Zone Vibe 100 input/output check.
- `frontend/realtime/src/audio/realtimeClient.ts` — AudioContext, AudioWorklet, and WebSocket lifecycle.
- `frontend/realtime/src/components/AudioStage.tsx` — real waveform and endpoint countdown.
- `frontend/realtime/src/components/TranscriptPanel.tsx` — locked, revisable, and partial text.
- `frontend/realtime/src/components/PipelineRail.tsx` — VAD/endpoint/queue/correction status.
- `frontend/realtime/src/components/DeviceGate.tsx` — hardware readiness and explicit controls.
- `frontend/realtime/src/vendor/reactbits/Waves.tsx`, `Waves.css`, `NOTICE.md` — copied upstream animation plus provenance.

### Deployment files to modify

- `Dockerfile` — Vite build stage and reusable CPU/NVIDIA Python image.
- `compose.yaml` — bootstrap, ASR worker, CPU llama.cpp worker, gateway dependencies, and hermetic frontend test service.
- `compose.gpu.yaml` — GPU image/runtime mapping only for ASR and llama.cpp workers.
- `docker/entrypoint.sh` — keep Piper bootstrap behavior and allow dedicated worker commands.
- `run.sh` — build/start/status/log/test the complete service topology.
- `.env.example`, `.gitignore`, `.dockerignore` — documented settings and generated/frontend/model exclusions.

### Tests to create

- `tests/test_realtime_models.py`
- `tests/test_realtime_audio.py`
- `tests/test_realtime_endpoint.py`
- `tests/test_realtime_queue.py`
- `tests/test_transcripts.py`
- `tests/test_text_inference.py`
- `tests/test_asr_worker.py`
- `tests/test_remote_asr.py`
- `tests/test_realtime.py`
- `tests/test_realtime_websocket.py`
- `tests/test_model_bootstrap.py`
- `frontend/realtime/src/state/reducer.test.ts`
- `frontend/realtime/src/audio/deviceGate.test.ts`
- `frontend/realtime/src/audio/realtimeClient.test.ts`
- `frontend/realtime/src/App.test.tsx`

### Existing tests to modify

- `tests/test_app.py` — capabilities and lifecycle injection.
- `tests/test_webui.py` — `/realtime` and immutable legacy routes.
- `tests/test_docker_runtime.py` — service isolation, GPU overrides, model mounts, and test hermeticity.
- `tests/test_operations.py` — additive API/spec/runtime documentation contract.
- `tests/test_production_providers.py` — warmup and remote-provider selection.

## Milestone 1 — Pure realtime domain logic

### Task 1: Add strict realtime models and validated settings

**Files:**
- Create: `src/agent_speak/realtime_models.py`
- Create: `tests/test_realtime_models.py`
- Modify: `src/agent_speak/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Write failing model and settings tests**

```python
# tests/test_realtime_models.py
from pydantic import ValidationError
import pytest

from agent_speak.config import Settings
from agent_speak.realtime_models import RealtimeEvent, StreamStart


def test_stream_start_accepts_only_approved_pcm_contract() -> None:
    start = StreamStart(type="stream.start", format="pcm_s16le", sample_rate=16_000, channels=1, frame_ms=20)
    assert start.model_dump() == {
        "type": "stream.start", "format": "pcm_s16le", "sample_rate": 16_000, "channels": 1, "frame_ms": 20
    }
    with pytest.raises(ValidationError):
        StreamStart(type="stream.start", format="float32", sample_rate=48_000, channels=2, frame_ms=100)


def test_realtime_event_requires_session_sequence_and_typed_payload() -> None:
    event = RealtimeEvent(sequence=1, session_id="session", utterance_id="utt", type="asr.partial", data={"text": "你好"})
    assert event.sequence == 1
    assert event.data["text"] == "你好"


def test_realtime_defaults_match_approved_design() -> None:
    settings = Settings()
    assert settings.realtime_frame_ms == 20
    assert settings.realtime_pre_roll_ms == 300
    assert settings.realtime_min_speech_ms == 250
    assert settings.realtime_partial_interval_ms == 800
    assert settings.realtime_endpoint_ms == 900
    assert settings.realtime_hard_endpoint_ms == 1800
    assert settings.realtime_endpoint_timeout_ms == 250
    assert settings.realtime_expected_device == "Zone Vibe 100"
    assert settings.asr_worker_url == ""
    assert settings.correction_worker_url == ""
    assert settings.effective_accelerator == "cpu"
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `python -m pytest tests/test_realtime_models.py -q`

Expected: collection fails because `agent_speak.realtime_models` does not exist.

- [ ] **Step 3: Implement strict transport/domain models**

```python
# src/agent_speak/realtime_models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field

from .schemas import StrictModel


class StreamStart(StrictModel):
    type: Literal["stream.start"]
    format: Literal["pcm_s16le"]
    sample_rate: Literal[16_000]
    channels: Literal[1]
    frame_ms: Literal[20, 40]


class StreamStop(StrictModel):
    type: Literal["stream.stop"]


class SessionPing(StrictModel):
    type: Literal["session.ping"]
    nonce: str = Field(min_length=1, max_length=128)


class RealtimeEvent(StrictModel):
    sequence: int = Field(ge=1)
    session_id: str = Field(min_length=1, max_length=128)
    utterance_id: str | None = Field(default=None, max_length=128)
    type: str = Field(min_length=1, max_length=128)
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CorrectionRevision:
    previous_text: str
    current_text: str
    changed: bool


@dataclass(frozen=True, slots=True)
class EndpointDecision:
    complete: bool
    reason: str
```

Add the approved settings to `Settings`, with Pydantic bounds that make invalid queue sizes, timing order, sample rates, and URLs fail at startup. Import `model_validator` from Pydantic and add this validator:

```python
realtime_frame_ms: Literal[20, 40] = 20
realtime_pre_roll_ms: int = Field(default=300, ge=0, le=2_000)
realtime_min_speech_ms: int = Field(default=250, ge=20, le=5_000)
realtime_partial_interval_ms: int = Field(default=800, ge=200, le=5_000)
realtime_endpoint_ms: int = Field(default=900, ge=200, le=5_000)
realtime_hard_endpoint_ms: int = Field(default=1_800, ge=400, le=10_000)
realtime_endpoint_timeout_ms: int = Field(default=250, ge=50, le=2_000)
realtime_max_utterance_seconds: float = Field(default=30.0, gt=0, le=300)
realtime_partial_queue: int = Field(default=8, ge=1, le=128)
realtime_final_queue: int = Field(default=8, ge=1, le=128)
realtime_text_queue: int = Field(default=8, ge=1, le=128)
realtime_expected_device: str = Field(default="Zone Vibe 100", min_length=1, max_length=200)
asr_worker_url: str = ""
correction_worker_url: str = ""
correction_model: str = "Qwen2.5-1.5B-Instruct-Q4_K_M"
effective_accelerator: Literal["cpu", "nvidia"] = "cpu"

@model_validator(mode="after")
def validate_realtime_contract(self) -> "Settings":
    if self.realtime_endpoint_ms >= self.realtime_hard_endpoint_ms:
        raise ValueError("realtime_endpoint_ms must be lower than realtime_hard_endpoint_ms")
    for name in ("asr_worker_url", "correction_worker_url"):
        value = getattr(self, name)
        if value and not value.startswith(("http://", "https://")):
            raise ValueError(f"{name} must be an HTTP(S) URL")
    return self
```

- [ ] **Step 4: Document every setting in `.env.example` and run GREEN**

Run: `python -m pytest tests/test_realtime_models.py tests/test_app.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit the domain contract**

```bash
git add src/agent_speak/realtime_models.py src/agent_speak/config.py tests/test_realtime_models.py .env.example
git commit -m "feat: define realtime stream contract"
```

### Task 2: Add PCM utilities and streaming VAD adapters

**Files:**
- Create: `src/agent_speak/realtime_audio.py`
- Create: `tests/test_realtime_audio.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing PCM and VAD tests**

```python
# tests/test_realtime_audio.py
import struct

import pytest

from agent_speak.errors import PlatformError
from agent_speak.realtime_audio import EnergyFrameVAD, PCMContract, pcm16_to_wav


def frame(amplitude: int, samples: int = 320) -> bytes:
    return struct.pack(f"<{samples}h", *([amplitude] * samples))


def test_pcm_contract_accepts_exact_20ms_frame_and_rejects_wrong_size() -> None:
    contract = PCMContract(sample_rate=16_000, channels=1, frame_ms=20)
    assert contract.validate(frame(1)) == frame(1)
    with pytest.raises(PlatformError, match="PCM frame"):
        contract.validate(frame(1, 319))


def test_pcm16_to_wav_produces_valid_mono_header() -> None:
    payload = pcm16_to_wav(frame(2000), sample_rate=16_000)
    assert payload[:4] == b"RIFF"
    assert payload[8:12] == b"WAVE"


def test_energy_fallback_separates_silence_and_voice() -> None:
    vad = EnergyFrameVAD(threshold=0.02)
    assert vad.score(frame(0)) == 0.0
    assert vad.score(frame(12_000)) > 0.5
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_realtime_audio.py -q`

Expected: import failure for `agent_speak.realtime_audio`.

- [ ] **Step 3: Implement bounded PCM conversion and fallback VAD**

```python
# core of src/agent_speak/realtime_audio.py
@dataclass(frozen=True, slots=True)
class PCMContract:
    sample_rate: int
    channels: int
    frame_ms: int

    @property
    def frame_bytes(self) -> int:
        return self.sample_rate * self.channels * 2 * self.frame_ms // 1000

    def validate(self, payload: bytes) -> bytes:
        if len(payload) != self.frame_bytes:
            raise PlatformError("invalid_pcm_frame", "PCM frame has an invalid byte length", stage="vad")
        return payload


def pcm16_to_wav(payload: bytes, *, sample_rate: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(payload)
    return output.getvalue()


class EnergyFrameVAD:
    def __init__(self, *, threshold: float) -> None:
        self.threshold = threshold

    def score(self, payload: bytes) -> float:
        samples = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
        return min(1.0, rms / self.threshold) if self.threshold else 0.0
```

Add `SileroFrameVAD` as a small adapter around `silero_vad.load_silero_vad(onnx=True)`. Buffer 512 samples before invoking the model, reset model state for each new stream, run ONNX on CPU, and return a float probability. Inject the model in tests; do not load/download it at import time.

Add runtime dependencies:

```toml
"httpx>=0.27,<1",
"silero-vad>=6,<7",
"onnxruntime>=1.20,<2",
```

- [ ] **Step 4: Prove Silero adapter state/reset using a fake model and run GREEN**

Run: `python -m pytest tests/test_realtime_audio.py tests/test_audio.py -q`

Expected: all selected tests pass without network or a real model.

- [ ] **Step 5: Commit audio primitives**

```bash
git add pyproject.toml src/agent_speak/realtime_audio.py tests/test_realtime_audio.py
git commit -m "feat: add streaming PCM and VAD primitives"
```

### Task 3: Implement the adaptive endpoint state machine

**Files:**
- Create: `src/agent_speak/realtime_endpoint.py`
- Create: `tests/test_realtime_endpoint.py`

- [ ] **Step 1: Write fake-clock state transition tests**

```python
# tests/test_realtime_endpoint.py
from agent_speak.realtime_endpoint import DetectorConfig, UtteranceDetector


def test_detector_emits_candidate_at_900ms_and_hard_final_at_1800ms() -> None:
    detector = UtteranceDetector(DetectorConfig(frame_ms=20, pre_roll_ms=300, min_speech_ms=250, endpoint_ms=900, hard_endpoint_ms=1800, max_utterance_ms=30_000))
    actions = []
    for _ in range(15):
        actions.extend(detector.accept(b"v" * 640, voiced=True))
    for _ in range(45):
        actions.extend(detector.accept(b"s" * 640, voiced=False))
    assert [item.kind for item in actions] == ["speech_started", "endpoint_candidate"]
    detector.extend_endpoint()
    actions = []
    for _ in range(45):
        actions.extend(detector.accept(b"s" * 640, voiced=False))
    assert actions[-1].kind == "utterance_final"


def test_resumed_speech_cancels_candidate_and_keeps_same_utterance() -> None:
    detector = UtteranceDetector(DetectorConfig.defaults())
    for _ in range(15):
        detector.accept(b"v" * 640, voiced=True)
    for _ in range(45):
        detector.accept(b"s" * 640, voiced=False)
    actions = detector.accept(b"v" * 640, voiced=True)
    assert [item.kind for item in actions] == ["endpoint_cancelled"]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_realtime_endpoint.py -q`

Expected: module import failure.

- [ ] **Step 3: Implement deterministic actions and bounded buffers**

Create immutable `DetectorConfig` and `DetectorAction(kind, utterance_id, pcm, silence_ms)` dataclasses. `UtteranceDetector.accept()` must:

- maintain a pre-roll deque capped at `pre_roll_ms`;
- ignore speech shorter than `min_speech_ms`;
- emit one `speech_started` per utterance;
- emit one `endpoint_candidate` at the baseline;
- cancel a candidate when speech resumes;
- let `extend_endpoint()` defer finalization only to the hard boundary;
- let `finalize_candidate()` emit the current PCM immediately;
- force `utterance_final` at the maximum utterance duration and begin a fresh pre-roll;
- clear all PCM on `reset()`.

```python
@dataclass(frozen=True, slots=True)
class DetectorAction:
    kind: Literal["speech_started", "endpoint_candidate", "endpoint_cancelled", "utterance_final"]
    utterance_id: str
    pcm: bytes = b""
    silence_ms: int = 0
```

- [ ] **Step 4: Cover noise rejection, pre-roll, max duration, reset, and GREEN**

Run: `python -m pytest tests/test_realtime_endpoint.py -q`

Expected: all endpoint tests pass.

- [ ] **Step 5: Commit endpoint logic**

```bash
git add src/agent_speak/realtime_endpoint.py tests/test_realtime_endpoint.py
git commit -m "feat: add adaptive realtime endpoint state machine"
```

### Task 4: Add bounded schedulers and transcript revision ledger

**Files:**
- Create: `src/agent_speak/realtime_queue.py`
- Create: `src/agent_speak/transcripts.py`
- Create: `tests/test_realtime_queue.py`
- Create: `tests/test_transcripts.py`

- [ ] **Step 1: Write scheduler and ledger tests**

```python
# tests/test_realtime_queue.py
import pytest

from agent_speak.realtime_queue import ASRJob, ASRScheduler, QueueFull


@pytest.mark.anyio
async def test_final_precedes_partial_and_new_partial_replaces_old_generation() -> None:
    queue = ASRScheduler(max_finals=2, max_partials=2)
    await queue.put_partial(ASRJob("session", "u1", 1, "partial", b"old"))
    await queue.put_partial(ASRJob("session", "u1", 2, "partial", b"new"))
    await queue.put_final(ASRJob("session", "u2", 1, "final", b"final"))
    assert (await queue.get()).mode == "final"
    partial = await queue.get()
    assert partial.generation == 2
    assert partial.pcm == b"new"


@pytest.mark.anyio
async def test_full_final_queue_raises_instead_of_dropping_audio() -> None:
    queue = ASRScheduler(max_finals=1, max_partials=1)
    await queue.put_final(ASRJob("s", "u1", 1, "final", b"one"))
    with pytest.raises(QueueFull):
        await queue.put_final(ASRJob("s", "u2", 1, "final", b"two"))
```

```python
# tests/test_transcripts.py
from agent_speak.realtime_models import CorrectionRevision
from agent_speak.transcripts import TranscriptLedger, stable_prefix


def test_stable_prefix_uses_consecutive_hypotheses() -> None:
    assert stable_prefix("我要去新竹", "我要去新竹科學園區") == "我要去新竹"


def test_only_previous_sentence_can_be_revised() -> None:
    ledger = TranscriptLedger()
    ledger.accept_final("u1", "第一句")
    ledger.accept_final("u2", "第二句")
    ledger.apply_revision("u2", CorrectionRevision("第一句已修正", "第二句已修正", True))
    ledger.accept_final("u3", "第三句")
    assert ledger.rows()[0].locked is True
    assert ledger.rows()[0].text == "第一句已修正"
    assert ledger.rows()[1].revisable is True
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_realtime_queue.py tests/test_transcripts.py -q`

Expected: both new modules are missing.

- [ ] **Step 3: Implement two explicit schedulers**

`ASRScheduler` uses a `deque` for finals and an insertion-ordered dict keyed by `(session_id, utterance_id)` for partials. Replacement must not grow the queue. `TextScheduler` uses separate endpoint and correction deques; `get()` always returns endpoint work first. Both schedulers use `asyncio.Condition`, expose queue depths, reject new work after `close()`, and never use unbounded `asyncio.create_task()` calls.

```python
@dataclass(frozen=True, slots=True)
class ASRJob:
    session_id: str
    utterance_id: str
    generation: int
    mode: Literal["partial", "final"]
    pcm: bytes


@dataclass(frozen=True, slots=True)
class TextJob:
    session_id: str
    utterance_id: str
    mode: Literal["endpoint", "correction"]
    previous_text: str
    current_text: str
```

- [ ] **Step 4: Implement stable-prefix and one-row revision invariants**

`TranscriptLedger` stores rows by utterance order. `accept_partial()` updates only the matching open utterance. `accept_final()` replaces its partial. `apply_revision(current_utterance_id, result)` may change the immediately preceding row plus the current row, then locks the preceding row. `finalize()` locks the last row. Any stale or unknown utterance raises `PlatformError("stale_transcript", "Transcript update is stale", stage="correction", retryable=False)` rather than mutating another sentence.

- [ ] **Step 5: Run GREEN and commit**

Run: `python -m pytest tests/test_realtime_queue.py tests/test_transcripts.py -q`

Expected: all selected tests pass.

```bash
git add src/agent_speak/realtime_queue.py src/agent_speak/transcripts.py tests/test_realtime_queue.py tests/test_transcripts.py
git commit -m "feat: schedule realtime inference safely"
```

## Milestone 2 — Isolated inference providers

### Task 5: Implement guarded llama.cpp endpoint and correction providers

**Files:**
- Create: `src/agent_speak/text_inference.py`
- Create: `tests/test_text_inference.py`
- Modify: `src/agent_speak/providers.py`
- Modify: `src/agent_speak/pipeline.py`

- [ ] **Step 1: Write failing prompt, schema, and guard tests**

```python
# tests/test_text_inference.py
import json

from agent_speak.text_inference import LlamaCppTextProvider


def response(content: dict[str, object]) -> dict[str, object]:
    return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}


def test_endpoint_uses_strict_json_and_preserves_reason() -> None:
    provider = LlamaCppTextProvider("http://worker:8080", "qwen", request=lambda _: response({"complete": False, "reason": "continuation"}))
    assert provider.detect("因為") == (False, "continuation")


def test_revision_preserves_numbers_english_and_code_tokens() -> None:
    provider = LlamaCppTextProvider(
        "http://worker:8080", "qwen",
        request=lambda _: response({"previous_text": "Python 3.11 使用 CUDA", "current_text": "延遲 900 ms", "changed": True}),
    )
    result = provider.revise("Python 3.11 使用 CUDA", "延遲 900 ms")
    assert result.current_text == "延遲 900 ms"


def test_excessive_or_protected_token_edit_falls_back_to_source() -> None:
    provider = LlamaCppTextProvider(
        "http://worker:8080", "qwen",
        request=lambda _: response({"previous_text": "刪除 Python 3.11", "current_text": "完全不同的新答案", "changed": True}),
    )
    result = provider.revise("保留 Python 3.11", "延遲 900 ms")
    assert result.previous_text == "保留 Python 3.11"
    assert result.current_text == "延遲 900 ms"
    assert result.changed is False
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_text_inference.py -q`

Expected: `text_inference` import failure.

- [ ] **Step 3: Add a revision-specific provider protocol**

```python
# addition to providers.py
@runtime_checkable
class RevisionProvider(Protocol):
    def revise(self, previous_text: str, current_text: str) -> CorrectionRevision:
        raise NotImplementedError
```

`LlamaCppTextProvider` implements `EndpointProvider`, `CorrectionProvider`, and `RevisionProvider`. `correct(text)` delegates to `revise("", text).current_text`, preserving existing `/api/v1/text/correct` behavior.

- [ ] **Step 4: Implement one bounded HTTP request path and strict response validation**

The provider posts to `${correction_worker_url}/v1/chat/completions` with `temperature=0`, bounded `max_tokens`, and a JSON schema response format. Inject `request(payload)` for tests; the production default uses a reusable `httpx.Client` with connect/read deadlines.

Use two fixed system prompts in this module: one returns `{complete, reason}`, the other returns `{previous_text, current_text, changed}`. Extract protected tokens with regular expressions for ASCII words, versions, integers/decimals, URLs, and backtick code. Reject output when protected tokens disappear or normalized edit distance exceeds the configured threshold.

- [ ] **Step 5: Wire configured provider selection without changing injected tests**

When `correction_worker_url` is non-empty, `ProviderSet.configured()` uses one `LlamaCppTextProvider` instance for `correction` and `endpoint`; otherwise it retains development providers for non-Compose local development. Capabilities must identify Qwen as non-development only after `/health` succeeds. The provider reports `cuda` only when `effective_accelerator=nvidia` was selected by `run.sh`, passed through Compose, and the worker health probe succeeds; otherwise it reports `cpu` or `unavailable`.

- [ ] **Step 6: Run GREEN and regression tests, then commit**

Run: `python -m pytest tests/test_text_inference.py tests/test_stage_api.py tests/test_app.py -q`

Expected: all selected tests pass; existing response shapes remain unchanged.

```bash
git add src/agent_speak/text_inference.py src/agent_speak/providers.py src/agent_speak/pipeline.py tests/test_text_inference.py tests/test_stage_api.py tests/test_app.py
git commit -m "feat: add guarded local text inference"
```

### Task 6: Add the internal ASR worker and provider-compatible client

**Files:**
- Create: `src/agent_speak/asr_worker.py`
- Create: `src/agent_speak/remote_asr.py`
- Create: `tests/test_asr_worker.py`
- Create: `tests/test_remote_asr.py`
- Modify: `src/agent_speak/production.py`
- Modify: `src/agent_speak/pipeline.py`

- [ ] **Step 1: Write failing worker and client tests**

```python
# tests/test_asr_worker.py
import httpx
import pytest

from agent_speak.asr_worker import create_asr_worker
from tests.audio_fixtures import wav_bytes


class FakeASR:
    device = "cuda"
    def warm(self) -> None: pass
    def transcribe(self, audio: bytes) -> str: return "即時測試"


@pytest.mark.anyio
async def test_internal_worker_warms_and_transcribes_bounded_wav() -> None:
    app = create_asr_worker(provider=FakeASR())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://worker") as client:
        health = await client.get("/internal/v1/health")
        result = await client.post("/internal/v1/asr?mode=final", content=wav_bytes(), headers={"content-type": "audio/wav"})
    assert health.json()["device"] == "cuda"
    assert result.json() == {"text": "即時測試", "device": "cuda", "mode": "final"}
```

```python
# tests/test_remote_asr.py
from agent_speak.remote_asr import RemoteASRProvider


def test_remote_asr_keeps_existing_provider_signature() -> None:
    provider = RemoteASRProvider("http://asr-worker:8771", request=lambda _: {"text": "你好", "device": "cuda"})
    assert provider.transcribe(b"RIFF-test-payload") == "你好"
    assert provider.device == "cuda"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_asr_worker.py tests/test_remote_asr.py -q`

Expected: missing worker/client modules.

- [ ] **Step 3: Add explicit Faster-Whisper warmup**

```python
# production.py
def warm(self) -> None:
    self._load_model()
```

The worker lifespan calls `warm()` through `run_sync`; readiness remains 503 until it succeeds. The worker accepts only `audio/wav`, applies the same byte/time bounds as the public API, and exposes only `/internal/v1/health` and `/internal/v1/asr`.

- [ ] **Step 4: Implement the sync provider client**

`RemoteASRProvider.transcribe()` posts bounded WAV to `?mode=final`. Add `transcribe_mode(audio, mode)` for realtime partial/final jobs. Convert network errors, non-200 responses, and invalid JSON into typed `PlatformError` values. Reuse one `httpx.Client`; do not create a client per partial request.

- [ ] **Step 5: Select remote ASR only when configured**

`ProviderSet.configured()` uses `RemoteASRProvider` when `asr_worker_url` is non-empty. Direct unit construction can pass an empty URL to retain `FasterWhisperASR`. Update capability tests to prove the actual worker-reported `device` is exposed.

- [ ] **Step 6: Run GREEN and commit**

Run: `python -m pytest tests/test_asr_worker.py tests/test_remote_asr.py tests/test_production_providers.py tests/test_stage_api.py -q`

Expected: all selected tests pass.

```bash
git add src/agent_speak/asr_worker.py src/agent_speak/remote_asr.py src/agent_speak/production.py src/agent_speak/pipeline.py tests/test_asr_worker.py tests/test_remote_asr.py tests/test_production_providers.py
git commit -m "feat: isolate Faster-Whisper worker"
```

## Milestone 3 — Realtime orchestration and WebSocket

### Task 7: Build the realtime coordinator and inference loops

**Files:**
- Create: `src/agent_speak/realtime.py`
- Create: `tests/test_realtime.py`
- Modify: `src/agent_speak/schemas.py`

- [ ] **Step 1: Write a full in-memory two-utterance test**

```python
# tests/test_realtime.py
import struct
import pytest

from agent_speak.realtime import RealtimeCoordinator


class FakeVAD:
    def score(self, frame: bytes) -> float: return 0.9 if any(frame) else 0.0
    def reset(self) -> None: pass


class FakeASR:
    def transcribe_mode(self, audio: bytes, mode: str) -> str:
        return "因為" if mode == "partial" else "因為需要測試"


class FakeText:
    def detect(self, text: str) -> tuple[bool, str]: return (not text.endswith("因為"), "semantic")
    def revise(self, previous: str, current: str):
        from agent_speak.realtime_models import CorrectionRevision
        return CorrectionRevision(previous, current + "。", True)


@pytest.mark.anyio
async def test_coordinator_streams_partial_final_revision_and_returns_to_listening() -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    stream = await coordinator.open("session")
    await stream.start()
    voice = struct.pack("<320h", *([10_000] * 320))
    silence = bytes(640)
    for _ in range(50): await stream.accept_pcm(voice)
    for _ in range(90): await stream.accept_pcm(silence)
    await stream.wait_idle()
    types = [event.type for event in stream.history]
    assert "asr.partial" in types
    assert "asr.final" in types
    assert "utterance.completed" in types
    assert stream.state == "listening"
    await coordinator.close()
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_realtime.py -q`

Expected: missing coordinator.

- [ ] **Step 3: Implement coordinator lifecycle with owned task set**

`RealtimeCoordinator` owns one `ASRScheduler`, one `TextScheduler`, a bounded session registry, and exactly one consumer task per queue. It exposes `start()`, `open(session_id)`, `close_stream(session_id, reason)`, and `close()`. Every task is retained in a set and awaited/cancelled on close.

`RealtimeStream` owns the PCM contract, VAD adapter, `UtteranceDetector`, partial interval counter, transcript ledger, monotonic event sequence, bounded event history, and subscriber queue. It exposes:

```python
async def start(self) -> None
async def accept_pcm(self, frame: bytes) -> None
async def stop(self, reason: str = "user") -> None
async def events(self) -> AsyncIterator[RealtimeEvent]
```

Do not route high-frequency `vad.level` events through `SessionBroker`; coalesce them in the realtime subscriber queue. Emit semantic transcript events into both realtime history and the existing session broker using `data={"utterance_id": event.utterance_id, "realtime_type": event.type, "text": event.data.get("text", "")}` so session inspection remains useful.

Implement `RealtimeCoordinator.for_test(vad, asr, text)` as a classmethod that constructs approved timings with fake providers and no model/network access. Implement `RealtimeStream.wait_idle()` with an `asyncio.Event` that is cleared when work is queued and set only when endpoint, ASR, and text jobs for that stream have completed; tests use it instead of sleeps.

- [ ] **Step 4: Implement partial/final/text result reconciliation**

- Snapshot partial PCM only after the configured interval.
- Convert PCM to WAV immediately before ASR dispatch.
- Ignore completed partial results whose generation is not current.
- On endpoint candidate, call the text scheduler with a 250 ms deadline; fallback to continuation markers.
- On final queue full, emit `pipeline.warning`, stop the stream after preserving the current utterance, and require explicit resume.
- Retry a failed final once; never retry partial work.
- Correction failure emits a warning and completes with raw final ASR.
- `stop()` finalizes voiced PCM, waits for bounded final/correction work, locks the newest transcript, clears ring buffers, and returns without Agent/TTS calls.

- [ ] **Step 5: Add failure, stale-result, queue-full, and shutdown tests**

Run: `python -m pytest tests/test_realtime.py tests/test_realtime_queue.py tests/test_transcripts.py -q`

Expected: all selected tests pass with no leaked asyncio task warnings.

- [ ] **Step 6: Commit coordinator**

```bash
git add src/agent_speak/realtime.py src/agent_speak/schemas.py tests/test_realtime.py
git commit -m "feat: orchestrate continuous realtime transcripts"
```

### Task 8: Add the binary-audio realtime WebSocket route

**Files:**
- Create: `src/agent_speak/realtime_routes.py`
- Create: `tests/test_realtime_websocket.py`
- Modify: `src/agent_speak/app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write ASGI WebSocket protocol tests**

```python
# tests/test_realtime_websocket.py
import asyncio
import json
from contextlib import suppress

import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings
from agent_speak.realtime import RealtimeCoordinator
from tests.test_realtime import FakeASR, FakeText, FakeVAD


@pytest.mark.anyio
async def test_realtime_socket_requires_start_before_binary_and_stops_cleanly(tmp_path) -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"), realtime=coordinator)
    session = await app.state.broker.create()
    incoming = asyncio.Queue()
    outgoing = []
    await incoming.put({"type": "websocket.connect"})
    await incoming.put({"type": "websocket.receive", "text": json.dumps({"type": "stream.start", "format": "pcm_s16le", "sample_rate": 16000, "channels": 1, "frame_ms": 20})})
    await incoming.put({"type": "websocket.receive", "bytes": bytes(640)})
    await incoming.put({"type": "websocket.receive", "text": json.dumps({"type": "stream.stop"})})
    await incoming.put({"type": "websocket.disconnect", "code": 1000})

    async def receive(): return await incoming.get()
    async def send(message): outgoing.append(message)

    await app({"type": "websocket", "path": f"/api/v1/realtime/sessions/{session.id}", "raw_path": b"", "query_string": b"", "headers": [], "client": ("test", 1), "server": ("test", 80), "scheme": "ws", "root_path": "", "subprotocols": [], "state": {}}, receive, send)
    sent = [json.loads(item["text"])["type"] for item in outgoing if item["type"] == "websocket.send" and "text" in item]
    assert "stream.accepted" in sent
    assert "stream.stopped" in sent
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_realtime_websocket.py -q`

Expected: the new route returns no acceptance event.

- [ ] **Step 3: Register an additive route with concurrent receive/send loops**

Extend `create_app()` with `realtime: RealtimeCoordinator | None = None`; injected coordinators keep WebSocket tests model-free. `register_realtime_routes(app)` adds `WS /api/v1/realtime/sessions/{session_id}`. Validate that the existing session exists before accept. Require a valid `StreamStart` text frame before binary PCM. Use one receiver task and one event-sender task; wait for first completion, cancel/await its peer, stop the stream, and close all microphone-related server state.

Typed close behavior:

```text
4400 invalid control JSON or PCM before start
4404 session not found
4408 frame timeout
4429 realtime capacity/backpressure
4500 internal realtime failure
```

The route never accepts base64 audio in JSON and never passes PCM through `SessionBroker`.

- [ ] **Step 4: Add invalid frame, unknown session, disconnect, and capacity tests**

Run: `python -m pytest tests/test_realtime_websocket.py tests/test_sessions_pipeline.py -q`

Expected: all selected tests pass and the existing session-events WebSocket is unchanged.

- [ ] **Step 5: Commit transport**

```bash
git add src/agent_speak/realtime_routes.py src/agent_speak/app.py tests/test_realtime_websocket.py tests/test_app.py
git commit -m "feat: stream bounded PCM over WebSocket"
```

## Milestone 4 — React/Vite Realtime Studio

### Task 9: Scaffold the isolated React application and static route

**Files:**
- Create: `frontend/realtime/package.json`
- Create: `frontend/realtime/package-lock.json`
- Create: `frontend/realtime/tsconfig.json`
- Create: `frontend/realtime/vite.config.ts`
- Create: `frontend/realtime/index.html`
- Create: `frontend/realtime/src/main.tsx`
- Create: `frontend/realtime/src/App.tsx`
- Create: `frontend/realtime/src/types.ts`
- Create: `frontend/realtime/src/App.test.tsx`
- Modify: `src/agent_speak/app.py`
- Modify: `tests/test_webui.py`

- [ ] **Step 1: Add a failing route test before creating frontend output**

```python
# addition to tests/test_webui.py
@pytest.mark.anyio
async def test_realtime_page_is_additive_and_legacy_pages_remain_unchanged(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        realtime = await client.get("/realtime")
        legacy = await client.get("/")
        codex = await client.get("/codex")
    assert realtime.status_code == 200
    assert '<div id="root"></div>' in realtime.text
    assert "Agent Speak" in legacy.text
    assert "Codex CLI" in codex.text
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_webui.py::test_realtime_page_is_additive_and_legacy_pages_remain_unchanged -q`

Expected: `/realtime` returns 404.

- [ ] **Step 3: Create a locked Vite toolchain**

Use npm and commit `package-lock.json`. `package.json` scripts are:

```json
{
  "scripts": {
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "lucide-react": "1.25.0",
    "ogl": "1.0.11",
    "react": "19.2.7",
    "react-dom": "19.2.7"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "6.9.1",
    "@testing-library/react": "16.3.2",
    "@types/react": "19.2.17",
    "@types/react-dom": "19.2.3",
    "@vitejs/plugin-react": "6.0.3",
    "jsdom": "29.1.1",
    "typescript": "7.0.2",
    "vite": "8.1.5",
    "vitest": "4.1.10"
  }
}
```

Generate and commit `package-lock.json` from exactly these versions. Set Vite `base: "/realtime/"` and output to `../../web/realtime` with `emptyOutDir: true`.

```ts
// frontend/realtime/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/realtime/',
  plugins: [react()],
  build: { outDir: '../../web/realtime', emptyOutDir: true },
  test: { environment: 'jsdom', setupFiles: './src/testSetup.ts' }
});
```

```json
// frontend/realtime/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable", "WebWorker"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src", "vite.config.ts"]
}
```

Add `frontend/realtime/node_modules/` and generated `web/realtime/` to both ignore policies. Docker copies its build-stage output explicitly; Git never tracks generated assets.

- [ ] **Step 4: Serve only built assets and preserve CSP**

Add `GET /realtime` returning `web/realtime/index.html` and mount `/realtime/assets` using `StaticFiles`. Do not add CDN origins or `unsafe-inline` to the normal CSP. If build output is absent, return a typed 503 in development instead of a blank page.

- [ ] **Step 5: Add a minimal React smoke test and build**

```tsx
// frontend/realtime/src/App.test.tsx
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { App } from './App';

test('renders the disabled realtime start control', () => {
  render(<App />);
  expect(screen.getByRole('button', { name: /開始即時聆聽/ })).toBeDisabled();
});
```

Run:

```bash
npm --prefix frontend/realtime test
npm --prefix frontend/realtime run build
python -m pytest tests/test_webui.py -q
```

Expected: Vitest, TypeScript/Vite build, and WebUI tests pass.

- [ ] **Step 6: Commit the scaffold and generated lockfile/assets policy**

```bash
git add frontend/realtime src/agent_speak/app.py tests/test_webui.py .gitignore .dockerignore
git commit -m "feat: add realtime React application"
```

### Task 10: Implement explicit device gating and AudioWorklet streaming

**Files:**
- Create: `frontend/realtime/public/pcm-capture.worklet.js`
- Create: `frontend/realtime/src/audio/deviceGate.ts`
- Create: `frontend/realtime/src/audio/deviceGate.test.ts`
- Create: `frontend/realtime/src/audio/realtimeClient.ts`
- Create: `frontend/realtime/src/audio/realtimeClient.test.ts`
- Create: `frontend/realtime/src/components/DeviceGate.tsx`
- Modify: `frontend/realtime/src/types.ts`

- [ ] **Step 1: Write failing device gate tests**

```ts
// frontend/realtime/src/audio/deviceGate.test.ts
import { describe, expect, it, vi } from 'vitest';
import { checkAudioDevices } from './deviceGate';

it('stops the temporary permission stream and requires matching input and output', async () => {
  const stop = vi.fn();
  const mediaDevices = {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }),
    enumerateDevices: vi.fn().mockResolvedValue([
      { kind: 'audioinput', deviceId: 'mic', label: 'Zone Vibe 100' },
      { kind: 'audiooutput', deviceId: 'out', label: 'Zone Vibe 100' }
    ])
  } as unknown as MediaDevices;
  const result = await checkAudioDevices(mediaDevices, 'Zone Vibe 100');
  expect(stop).toHaveBeenCalledOnce();
  expect(result.ready).toBe(true);
});

it('keeps start disabled when either endpoint is absent', async () => {
  const stop = vi.fn();
  const mediaDevices = {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }),
    enumerateDevices: vi.fn().mockResolvedValue([
      { kind: 'audioinput', deviceId: 'mic', label: 'Zone Vibe 100' }
    ])
  } as unknown as MediaDevices;
  const result = await checkAudioDevices(mediaDevices, 'Zone Vibe 100');
  expect(stop).toHaveBeenCalledOnce();
  expect(result).toMatchObject({ ready: false, reason: 'missing_output' });
});
```

- [ ] **Step 2: Run RED**

Run: `npm --prefix frontend/realtime test -- deviceGate.test.ts`

Expected: missing module failure.

- [ ] **Step 3: Implement permission-safe device discovery**

`checkAudioDevices()` calls `getUserMedia({audio: true, video: false})`, enumerates devices only after labels are available, and stops every temporary track in `finally`. Match device labels case-insensitively. Return `{ready, input, output, reason}`; never play sound. Export a `watchDeviceChanges()` helper that invalidates the gate and returns an unsubscribe function.

- [ ] **Step 4: Write failing client lifecycle tests**

Test that `RealtimeClient.start()` refuses an unapproved gate, sends `stream.start` before binary frames, and that `stop()`, socket close, worklet error, or device invalidation stops every track, disconnects nodes, closes the AudioContext, and never reconnects automatically.

- [ ] **Step 5: Implement worklet and client**

The worklet downsamples input to 16 kHz mono, clamps samples to `[-1, 1]`, converts to little-endian PCM16, and posts exactly 320 samples per 20 ms frame. It also posts a small waveform envelope for the UI; raw audio is sent only as transferable `ArrayBuffer` frames over the open WebSocket.

`RealtimeClient` owns one stream/socket/context/worklet tuple, exposes `checkDevices()`, `start(sessionId)`, and `stop(reason)`, and emits typed UI events. It must not construct `getUserMedia` or an `AudioContext` during module import or React render.

- [ ] **Step 6: Run GREEN and commit**

Run: `npm --prefix frontend/realtime test -- deviceGate.test.ts realtimeClient.test.ts`

Expected: all audio lifecycle tests pass in jsdom with mocked browser APIs.

```bash
git add frontend/realtime/public/pcm-capture.worklet.js frontend/realtime/src/audio frontend/realtime/src/components/DeviceGate.tsx frontend/realtime/src/types.ts
git commit -m "feat: gate realtime browser audio explicitly"
```

### Task 11: Build Realtime Studio state, transcript, pipeline, and motion UI

**Files:**
- Create: `frontend/realtime/src/state/reducer.ts`
- Create: `frontend/realtime/src/state/reducer.test.ts`
- Create: `frontend/realtime/src/components/AudioStage.tsx`
- Create: `frontend/realtime/src/components/TranscriptPanel.tsx`
- Create: `frontend/realtime/src/components/PipelineRail.tsx`
- Create: `frontend/realtime/src/vendor/reactbits/Waves.tsx`
- Create: `frontend/realtime/src/vendor/reactbits/Waves.css`
- Create: `frontend/realtime/src/vendor/reactbits/NOTICE.md`
- Modify: `frontend/realtime/src/App.tsx`
- Modify: `frontend/realtime/src/App.test.tsx`
- Modify: `frontend/realtime/src/styles.css`

- [ ] **Step 1: Write reducer tests for ordered utterance reconciliation**

```ts
// frontend/realtime/src/state/reducer.test.ts
import { initialState, realtimeReducer } from './reducer';

test('ignores duplicate sequence and never mixes utterance partials', () => {
  const one = realtimeReducer(initialState, { sequence: 2, session_id: 's', utterance_id: 'u1', type: 'asr.partial', at: '', data: { text: '第一' } });
  const duplicate = realtimeReducer(one, { sequence: 2, session_id: 's', utterance_id: 'u2', type: 'asr.partial', at: '', data: { text: '錯誤' } });
  expect(duplicate).toBe(one);
  const two = realtimeReducer(one, { sequence: 3, session_id: 's', utterance_id: 'u2', type: 'asr.partial', at: '', data: { text: '第二' } });
  expect(two.rows.find(row => row.utteranceId === 'u1')?.text).toBe('第一');
  expect(two.rows.find(row => row.utteranceId === 'u2')?.text).toBe('第二');
});
```

- [ ] **Step 2: Run RED, then implement a discriminated reducer**

Run: `npm --prefix frontend/realtime test -- reducer.test.ts`

Expected: missing reducer.

The reducer tracks connection, device gate, stream state, current VAD level, endpoint countdown, ASR queue depth, correction state, latency metrics, dropped frames, and rows keyed by `utterance_id`. `transcript.revised` may update only the current row and its immediate predecessor. Duplicate/out-of-order sequence values are ignored.

- [ ] **Step 3: Copy and document the upstream React Bits component**

Copy the TypeScript/CSS `Waves` implementation from `DavidHDev/react-bits` into `src/vendor/reactbits/`, record the exact upstream commit, source URLs, and license in `NOTICE.md`, and keep it visually subordinate. Do not fetch component code at runtime.

- [ ] **Step 4: Implement the approved layout and semantic motion**

- One primary action: check devices before readiness, start when ready, stop while active.
- Actual waveform canvas uses local envelope samples, not React Bits.
- Transcript rows visibly distinguish locked, revisable, and partial text.
- Pipeline rail labels VAD, endpoint, queue depth, correction, and actual worker devices.
- State colors include icons/text and meet contrast requirements.
- Every interactive element is keyboard reachable with visible focus and at least 44×44 px.
- `aria-live="polite"` announces device/state changes without stealing focus.
- At 375/768 px, status cards move below waveform/transcript without horizontal scrolling.
- `prefers-reduced-motion` disables Waves, shimmer, and nonessential transitions.

- [ ] **Step 5: Add UI behavior/accessibility tests**

Add these concrete component assertions to `App.test.tsx`, using a mocked `RealtimeClient` module whose `checkDevices`, `start`, and `stop` methods are `vi.fn()` values:

```tsx
test('gates start, exposes stop only while active, and labels transcript states', async () => {
  const { rerender } = render(<App />);
  expect(screen.getByRole('button', { name: /開始即時聆聽/ })).toBeDisabled();
  expect(screen.queryByRole('button', { name: /停止即時聆聽/ })).not.toBeInTheDocument();
  expect(screen.getByText(/尚未檢查 Zone Vibe 100/)).toBeInTheDocument();
  // Dispatch the exported device-ready and transcript fixture events through the mocked client.
  emitFixture({ type: 'device.ready', data: { input: 'Zone Vibe 100', output: 'Zone Vibe 100' } });
  emitFixture({ sequence: 2, session_id: 's', utterance_id: 'u1', type: 'asr.partial', at: '', data: { text: '暫定文字' } });
  rerender(<App />);
  expect(screen.getByText('暫定文字')).toHaveAccessibleName(/暫定文字/);
  expect(screen.getByRole('button', { name: /開始即時聆聽/ })).toBeEnabled();
});

test('error and reduced-motion modes remain textual', () => {
  render(<App forceReducedMotion />);
  emitFixture({ type: 'pipeline.error', data: { message: 'ASR worker unavailable' } });
  expect(screen.getByRole('alert')).toHaveTextContent('ASR worker unavailable');
  expect(screen.getByTestId('ambient-waves')).toHaveAttribute('data-animated', 'false');
});
```

Define `AppProps.forceReducedMotion?: boolean` and export the test-only event sink from the mocked client setup file; production code continues to use `matchMedia('(prefers-reduced-motion: reduce)')`.

Run:

```bash
npm --prefix frontend/realtime test
npm --prefix frontend/realtime run build
```

Expected: all Vitest tests and the production build pass.

- [ ] **Step 6: Commit the approved UI**

```bash
git add frontend/realtime
git commit -m "feat: render realtime speech studio"
```

## Milestone 5 — Docker topology, lifecycle, and acceptance

### Task 12: Add model bootstrap and CPU/GPU worker topology

**Files:**
- Create: `scripts/bootstrap_models.py`
- Create: `tests/test_model_bootstrap.py`
- Modify: `Dockerfile`
- Modify: `compose.yaml`
- Modify: `compose.gpu.yaml`
- Modify: `docker/entrypoint.sh`
- Modify: `run.sh`
- Modify: `tests/test_docker_runtime.py`

- [ ] **Step 1: Write failing static topology tests**

```python
# additions to tests/test_docker_runtime.py
def test_realtime_workers_are_internal_and_gpu_override_targets_inference_only() -> None:
    base = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    gpu = yaml.safe_load((ROOT / "compose.gpu.yaml").read_text(encoding="utf-8"))
    assert set(("model-bootstrap", "asr-worker", "correction-worker")) <= base["services"].keys()
    assert "ports" not in base["services"]["asr-worker"]
    assert "ports" not in base["services"]["correction-worker"]
    assert gpu["services"]["asr-worker"]["runtime"] == "nvidia"
    assert gpu["services"]["correction-worker"]["runtime"] == "nvidia"
    assert "gateway" not in gpu["services"] or "runtime" not in gpu["services"]["gateway"]
    assert "/dev/snd" not in base["services"]["asr-worker"].get("devices", [])


def test_test_services_have_no_audio_gpu_models_or_network() -> None:
    config = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    for name in ("gateway-test", "frontend-test"):
        service = config["services"][name]
        assert service["network_mode"] == "none"
        assert "devices" not in service
        assert not service.get("volumes")
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_docker_runtime.py -q`

Expected: worker services are absent or the GPU remains mapped to Gateway.

- [ ] **Step 3: Add idempotent model bootstrap tests and implementation**

`tests/test_model_bootstrap.py` injects fake `download_model` and `hf_hub_download` callables. Prove cached paths perform zero downloads and missing paths download exactly:

```text
Faster-Whisper: configured AGENT_SPEAK_ASR_MODEL
Qwen repo: Qwen/Qwen2.5-1.5B-Instruct-GGUF
Qwen file: qwen2.5-1.5b-instruct-q4_k_m.gguf
```

`scripts/bootstrap_models.py` writes only beneath `/app/models`, uses the existing Hugging Face cache, verifies the final file exists and is non-empty, and never prints credentials. Add an explicit `AGENT_SPEAK_SKIP_MODEL_BOOTSTRAP=1` path for hermetic tests.

- [ ] **Step 4: Build the frontend in a pinned Node stage**

Add a `node:22-bookworm-slim` stage that copies `package.json` and `package-lock.json`, runs `npm ci`, copies frontend source, runs `npm test` in the frontend-test target, and runs `npm run build` for production. Copy only `web/realtime` build output into the Python runtime image. Do not copy `node_modules` into runtime.

- [ ] **Step 5: Define the base CPU services**

`compose.yaml` must include:

- `model-bootstrap`: one-shot Agent Speak image, models mount only, no `/dev/snd`, command `python scripts/bootstrap_models.py`.
- `asr-worker`: Agent Speak CPU image, models mount, internal port 8771 only, command `uvicorn agent_speak.asr_worker:create_asr_worker --factory`, healthcheck `/internal/v1/health`.
- `correction-worker`: `ghcr.io/ggml-org/llama.cpp:server`, models mount, internal port 8080 only, Qwen model path, context 4096, parallel 1, bounded prediction tokens, healthcheck `/health`.
- `gateway`: current data/runtime/models/audio mappings, internal worker URLs, and health dependencies after bootstrap/workers.
- `gateway-test`: no network, audio, model, runtime, or production mounts.
- `frontend-test`: Node test target, no network or production mounts.

Use image variables with safe defaults so deployments can pin digests without editing Compose:

```yaml
image: "${AGENT_SPEAK_LLAMA_CPU_IMAGE:-ghcr.io/ggml-org/llama.cpp:server}"
```

- [ ] **Step 6: Restrict GPU override to inference workers**

`compose.gpu.yaml` sets the NVIDIA Agent Speak build/image on `asr-worker`, `ghcr.io/ggml-org/llama.cpp:server-cuda` on `correction-worker`, and applies both `runtime: nvidia` plus the Compose GPU reservation to those two services only. Gateway, bootstrap, and tests remain CPU-safe and receive no GPU reservation.

- [ ] **Step 7: Update lifecycle operations and status**

- `--build`, `--up`, restart, rebuild, and down operate on the full topology.
- `wait_for_health` checks bootstrap completion plus both workers and Gateway.
- `--status` prints capture/playback, selected accelerator, `asr_device`, `correction_device`, queue readiness, and `/realtime` URL.
- `--logs` includes Gateway plus both inference workers without exposing transcripts.
- `--test` runs `gateway-test` then `frontend-test` and prints `TESTS_OK` only after both pass.
- Auto fallback selects base CPU Compose; strict NVIDIA failure remains unchanged.

After `configure_accelerator`, `run.sh` exports `AGENT_SPEAK_EFFECTIVE_ACCELERATOR=$ACCELERATOR_SELECTED`. Compose passes that value to Gateway and both Agent Speak worker containers. Unit tests extend `_accelerator_env()` so CPU fallback reports `effective_accelerator=cpu` and successful NVIDIA preflight reports `effective_accelerator=nvidia`.

- [ ] **Step 8: Run static GREEN, merged Compose validation, and commit**

Run:

```bash
bash -n run.sh docker/entrypoint.sh
docker compose -f compose.yaml config >/dev/null
docker compose -f compose.yaml -f compose.gpu.yaml config >/dev/null
python -m pytest tests/test_docker_runtime.py tests/test_model_bootstrap.py tests/test_accelerators.py -q
```

Expected: shell syntax, both Compose configurations, and all selected tests pass.

```bash
git add Dockerfile compose.yaml compose.gpu.yaml docker/entrypoint.sh run.sh scripts/bootstrap_models.py tests/test_model_bootstrap.py tests/test_docker_runtime.py
git commit -m "feat: deploy isolated realtime inference workers"
```

### Task 13: Complete docs, integration regression, and real acceptance

**Files:**
- Modify: `README.md`
- Modify: `README.zh-TW.md`
- Modify: `spec/API.md`
- Modify: `spec/ARCHITECTURE.md`
- Modify: `spec/RUNTIME.md`
- Modify: `spec/TESTING.md`
- Modify: `spec/UI.md`
- Modify: `spec/project_herness.md`
- Modify: `spec/references/MODEL_STRATEGY.md`
- Modify: `tests/test_docs.py`
- Modify: `tests/test_operations.py`
- Modify: `tests/test_webui.py`

- [ ] **Step 1: Write failing documentation contract tests**

Tests assert that public docs state:

- `/realtime` is continuous transcription only;
- microphone start is explicit and gated by Zone Vibe 100 input/output visibility;
- output visibility is not proof of physical playback;
- WebSocket carries raw audio while MCP remains control-only;
- partial text can change, the previous sentence is revisable, and older sentences lock;
- endpoint timing is 900–1,800 ms;
- correction is local Qwen and can fall back to raw final ASR;
- no Agent, TTS, Codex injection, recording persistence, or automatic reconnect is claimed;
- CPU is functional and GPU latency targets are host-specific.

- [ ] **Step 2: Run RED, update documentation, and run GREEN**

Run: `python -m pytest tests/test_docs.py tests/test_operations.py tests/test_webui.py -q`

Expected before edits: missing realtime contract assertions. Expected after edits: all selected tests pass.

- [ ] **Step 3: Rebuild and run the complete hermetic regression**

Run:

```bash
docker compose -f compose.yaml build gateway-test frontend-test
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --test
```

Expected: all pytest and Vitest tests pass, legacy JavaScript checks pass, and output ends with `TESTS_OK`.

- [ ] **Step 4: Verify CPU topology without microphone or playback**

Run:

```bash
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --down_up
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --status
```

Expected: Gateway and both workers are healthy; `asr_device=cpu`, `correction_device=cpu`; no microphone capture or speaker playback command is invoked.

- [ ] **Step 5: Verify real GPU workers without microphone or playback**

Run only after Docker/model network approval:

```bash
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --rebuild
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --status
docker compose -f compose.yaml -f compose.gpu.yaml exec -T asr-worker nvidia-smi -L
docker compose -f compose.yaml -f compose.gpu.yaml exec -T correction-worker nvidia-smi -L
```

Expected: status reports `accelerator=nvidia`, `asr_device=cuda`, and `correction_device=cuda`; both workers see the NVIDIA GPU.

- [ ] **Step 6: Run a synthetic realtime WebSocket acceptance test**

Create `scripts/realtime_smoke.py`. It must generate PCM in memory, never access `/dev/snd`, create a session, stream voiced/silent frames, and assert ordered `vad.speech_started`, `asr.final`, `transcript.revised` or raw fallback, `utterance.completed`, and return to listening.

Use Piper only as an in-memory speech fixture; do not call the TTS API, store an artifact, or play it. The script structure is:

```python
from __future__ import annotations

import argparse
import asyncio
import io
import json
from pathlib import Path
import wave

import httpx
import numpy as np
import websockets

from agent_speak.production import PiperTTS


def pcm16_fixture(model_path: str, text: str) -> bytes:
    wav = PiperTTS(model_path=Path(model_path)).synthesize(text)
    with wave.open(io.BytesIO(wav), "rb") as source:
        rate = source.getframerate()
        samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
    positions = np.linspace(0, len(samples) - 1, round(len(samples) * 16_000 / rate))
    converted = np.interp(positions, np.arange(len(samples)), samples).astype("<i2")
    return converted.tobytes()


async def run(base_url: str, model_path: str) -> None:
    with httpx.Client(base_url=base_url, timeout=10) as client:
        session_id = client.post("/api/v1/sessions").raise_for_status().json()["id"]
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    events: list[str] = []
    async with websockets.connect(f"{ws_url}/api/v1/realtime/sessions/{session_id}", max_size=1_048_576) as socket:
        await socket.send(json.dumps({"type": "stream.start", "format": "pcm_s16le", "sample_rate": 16000, "channels": 1, "frame_ms": 20}))
        pcm = pcm16_fixture(model_path, "這是一段即時語音辨識測試")
        for offset in range(0, len(pcm) - 639, 640):
            await socket.send(pcm[offset:offset + 640])
        for _ in range(90):
            await socket.send(bytes(640))
        while "utterance.completed" not in events:
            event = json.loads(await asyncio.wait_for(socket.recv(), timeout=30))
            events.append(event["type"])
        await socket.send(json.dumps({"type": "stream.stop"}))
    required = ["vad.speech_started", "asr.final", "utterance.completed"]
    positions = [events.index(name) for name in required]
    if positions != sorted(positions):
        raise RuntimeError(f"Realtime events are out of order: {events}")
    print("REALTIME_SMOKE_OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--piper-model", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.piper_model))


if __name__ == "__main__":
    main()
```

Run:

```bash
docker compose exec -T gateway python scripts/realtime_smoke.py \
  --url http://127.0.0.1:8765 \
  --piper-model /app/models/piper/zh_CN-huayan-medium.onnx
```

Expected: `REALTIME_SMOKE_OK`; no audio file is written and no sound is played.

- [ ] **Step 7: Request explicit consent before physical browser acceptance**

Do not proceed until the user explicitly authorizes microphone use. After consent, open `/realtime`, press **Check devices**, verify both Zone Vibe 100 endpoints, then explicitly press **Start realtime listening**. Do not press or implement a speaker-test action in this release.

Acceptance checklist:

- hardware check immediately stops its temporary stream;
- start stays disabled if either endpoint is absent;
- live waveform responds under 100 ms;
- VAD starts near 200 ms;
- partial text appears after warmup within the 1.5-second target;
- 900 ms endpoint candidate and semantic extension are visible;
- hard endpoint occurs at 1,800 ms;
- final/correction target is within 2 seconds on the verified RTX 2080 Ti;
- the next utterance starts without another click;
- device removal and WebSocket loss stop microphone tracks;
- no Agent, TTS, playback, or persisted audio occurs.

- [ ] **Step 8: Run final repository checks and commit docs**

Run:

```bash
git diff --check
git status --short
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --test
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --status
```

Expected: no whitespace errors; only intentional files are changed; full regression passes; running stack is healthy.

```bash
git add README.md README.zh-TW.md spec tests/test_docs.py tests/test_operations.py tests/test_webui.py scripts/realtime_smoke.py
git commit -m "docs: explain realtime speech studio"
```

## Completion checklist

- [ ] Existing public REST/MCP/WebUI contracts remain green.
- [ ] Realtime logic has deterministic fake-clock and fake-provider tests.
- [ ] No unbounded queue, task, audio buffer, event history, or transcript history exists.
- [ ] Worker ports are internal-only and neither worker maps `/dev/snd`.
- [ ] CPU and NVIDIA Compose paths are both validated.
- [ ] Actual provider devices, queue state, and degraded latency are visible.
- [ ] React UI meets keyboard, contrast, target-size, responsive, and reduced-motion requirements.
- [ ] React Bits provenance and license are present.
- [ ] Model weights, generated Vite dependencies, audio, runtime, and `.superpowers/` remain untracked.
- [ ] Physical microphone acceptance was either explicitly authorized and completed, or clearly reported as not run.
- [ ] No speaker playback, Agent invocation, or Codex injection occurs.
