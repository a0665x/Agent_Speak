# Realtime Speech Studio Design

Date: 2026-07-20
Status: Approved design
Route: `http://127.0.0.1:8765/realtime`

## Objective

Add a local, continuous transcription demo to Agent Speak. After an explicit hardware check and an explicit start action, the browser continuously streams microphone audio to the Gateway. The Gateway performs realtime VAD, adaptive endpoint detection, rolling partial ASR, final ASR, local Chinese text correction, and ordered UI updates. After each utterance it automatically returns to listening until the operator stops the stream.

The first release ends at the corrected transcript. It does not inject text into Codex, invoke an Agent, synthesize speech, or play through the speaker.

## Approved product decisions

- Add React, TypeScript, and Vite for the new `/realtime` application.
- Use the information-dense **Realtime Studio** layout rather than a voice orb or transcript-only layout.
- Show rolling partial transcripts while speech is in progress.
- Use a 900 ms silence baseline for endpoint detection, extend semantically incomplete Mandarin up to a hard 1,800 ms silence boundary, and then finalize.
- Keep the newest finalized sentence revisable until the following sentence supplies context; older sentences are locked.
- Run a lightweight local correction model rather than an external API.
- Isolate ASR and correction inference from the Gateway event loop.
- Preserve the existing `/api/v1` REST contracts, provider boundaries, `/`, and `/codex`.
- Require an explicit device check and explicit start action. Never start the microphone or speaker automatically.

## Scope

### Included

- `/realtime` React application built by Vite and served by FastAPI.
- Browser `AudioWorklet` capture as 16 kHz mono PCM frames.
- A realtime binary-audio WebSocket under `/api/v1`.
- Continuous VAD with pre-roll and bounded utterance buffers.
- Adaptive endpoint detection with 900–1,800 ms silence behavior.
- Rolling partial Faster-Whisper inference and final utterance inference.
- Bounded priority scheduling and observable backpressure.
- Local Qwen2.5 1.5B correction through llama.cpp.
- One-sentence Chinese revision window.
- Realtime pipeline state, queue, device, latency, and transcript UI.
- CPU fallback plus actual CUDA-device reporting.
- Unit, contract, browser, CPU-container, and real-GPU acceptance tests.

### Excluded

- Codex CLI session injection or automated keyboard input.
- External-Agent reasoning.
- TTS or physical speaker playback.
- Speaker identification or authentication decisions.
- Persisted recordings or raw audio history.
- Multi-user distributed queues, Redis, or cross-host workers.
- Native mobile applications.

## System architecture

```text
React /realtime
  │ AudioWorklet: 16 kHz mono PCM, 20–40 ms/frame
  │ WebSocket: binary audio + JSON control
  ▼
Gateway
  ├─ realtime session registry
  ├─ VAD ring buffer
  ├─ adaptive endpoint state machine
  ├─ bounded priority scheduler
  └─ ordered realtime events
       │
       ├─ ASR Worker
       │    ├─ rolling partial ASR
       │    └─ endpoint final ASR
       │
       └─ Correction Worker
            └─ Qwen2.5-1.5B-Instruct Q4_K_M
```

### React client

The React client owns permission prompts, device selection, the `AudioWorklet`, local waveform rendering, transport controls, transcript reconciliation, and presentation. It never decides that server-side ASR or correction succeeded merely from animation state.

The `AudioWorklet` emits PCM16 frames every 20–40 ms. The visible audio waveform is driven by actual Web Audio samples on the client and stays responsive even when server inference is busy.

### Gateway

The Gateway owns session lifecycle, frame validation, VAD, utterance buffering, endpoint timing, job scheduling, event ordering, resource limits, and failure mapping. No model inference runs on the FastAPI event loop.

The in-memory schedulers are sufficient for this single-host release. Redis is intentionally excluded. A Gateway restart ends active realtime sessions rather than claiming to recover audio that no longer exists.

### ASR Worker

The ASR Worker is an internal-only service that loads Faster-Whisper through the existing ASR provider boundary. It accepts bounded utterance snapshots for partial or final transcription. The Compose service has no published host port.

Pending partial jobs for the same utterance are replaceable. Final jobs are never silently discarded. ASR queue priority is:

```text
final ASR > newest partial ASR
```

The model is warmed during worker readiness so the first spoken utterance does not pay the full lazy-load latency.

### Correction Worker

The correction service uses the official `Qwen/Qwen2.5-1.5B-Instruct-GGUF` Q4_K_M model through a CUDA-enabled llama.cpp server. The Q4_K_M artifact is approximately 1.12 GB and supports Chinese and English. Thin typed adapters expose the same internal model through the existing endpoint and correction provider boundaries. The service is internal-only.

The text scheduler has a separate bounded queue with this priority:

```text
endpoint decision > transcript correction
```

An already-running correction is not force-killed. A queued endpoint decision moves ahead of queued corrections; if it cannot finish within the endpoint deadline, deterministic continuation rules decide whether to extend the silence window.

Correction requests use schema-constrained JSON. The prompt permits ASR spelling, segmentation, and punctuation repairs only. It forbids answering, summarizing, adding facts, or rewriting uncertain names, numbers, English, code, and technical terms.

The Gateway validates correction output before accepting it. Invalid JSON, excessive edit distance, lost protected tokens, added information, or timeout causes a warning and preserves final ASR text.

### Accelerator behavior

`AGENT_SPEAK_ACCELERATOR=auto|cpu|nvidia` applies to both inference workers:

- `auto`: select NVIDIA only after host and Docker runtime preflight; otherwise use CPU.
- `cpu`: force CPU images and CPU inference.
- `nvidia`: require the NVIDIA runtime and fail clearly if unavailable.

Capabilities and realtime events report the actual ASR and correction devices independently. CPU mode is functional but the UI labels it as degraded when measured latency exceeds the realtime target.

## Transport contract

### Session creation

The existing `POST /api/v1/sessions` remains unchanged. The realtime client creates a normal session, then connects to:

```text
WS /api/v1/realtime/sessions/{session_id}
```

This is an additive `/api/v1` contract. Raw realtime audio remains on the HTTP/WebSocket data plane and never travels through MCP JSON-RPC.

### Client messages

JSON control messages are text WebSocket frames:

```json
{"type":"stream.start","format":"pcm_s16le","sample_rate":16000,"channels":1,"frame_ms":20}
{"type":"stream.stop"}
{"type":"session.ping","nonce":"..."}
```

After `stream.accepted`, binary WebSocket frames contain little-endian signed PCM16 only. Frames arriving before acceptance, after stop, with an invalid length, or above configured rates close the stream with a typed error.

### Server event envelope

```json
{
  "sequence": 42,
  "session_id": "...",
  "utterance_id": "...",
  "type": "asr.partial",
  "timestamp": "2026-07-20T12:34:56.789Z",
  "payload": {}
}
```

Events are ordered within one realtime session. The main event types are:

```text
device.ready
stream.accepted
stream.started
vad.speech_started
vad.level
endpoint.candidate
endpoint.extended
asr.queued
asr.processing
asr.partial
asr.final
correction.processing
transcript.revised
utterance.completed
stream.stopped
pipeline.warning
pipeline.error
```

High-rate `vad.level` events are coalesced and are not retained in session history. Semantic state changes and transcript events are retained within existing bounded session limits.

## Realtime state machine

```text
ready
 → listening
 → speech_started
 → transcribing_partial
 → endpoint_candidate
 → finalizing
 → correcting
 → listening
```

### VAD

- Primary provider: Silero VAD ONNX.
- Fallback provider: existing deterministic Energy VAD.
- Pre-roll: 300 ms.
- Minimum voiced duration: 250 ms.
- Frames remain bounded in an in-memory ring buffer.
- A single utterance is capped at 30 seconds. The Gateway finalizes that segment and immediately begins the next one without stopping the realtime session.

### Endpoint detection

Silence reaching 900 ms creates an endpoint candidate. The Gateway sends the latest partial transcript to the Qwen-backed endpoint provider and requires schema-constrained `{complete, reason}` JSON within a default 250 ms deadline. Obvious Mandarin continuation markers such as `因為`, `所以`, `但是`, `然後`, `如果`, and `以及` provide a deterministic fallback when the provider is late, invalid, or unavailable.

An incomplete decision extends the candidate without exceeding 1,800 ms of silence. Resumed speech cancels the candidate. At 1,800 ms the utterance finalizes regardless of the semantic decision.

### Rolling partial transcription

After speech begins, the scheduler snapshots the current utterance about every 800 ms. Newer pending partial work for the same utterance replaces older pending work. Running inference is not force-killed; its result is ignored if its generation is stale.

Each partial snapshot re-transcribes the current utterance to gain Mandarin context. The Gateway compares consecutive hypotheses to identify a stable common prefix. The UI renders stable text normally and the mutable suffix with a subdued revision treatment. Endpoint finalization always performs one full final transcription and replaces the partial hypothesis.

### Chinese revision window

For utterances `N-1` and `N`:

1. Final ASR for `N-1` remains revisable.
2. When final ASR for `N` arrives, correction receives both sentences and bounded terminology context.
3. Correction may repair `N-1` using the new context.
4. After validation, `N-1` locks and `N` becomes revisable.
5. Stopping the stream runs the last bounded correction and locks the newest sentence.

The correction schema is:

```json
{
  "previous_text": "已重新確認的上一句",
  "current_text": "目前校正句",
  "changed": true
}
```

## Hardware and consent gate

The primary start button is disabled on page load. The operator must press **Check devices** first.

1. The browser explicitly requests microphone permission.
2. Once device labels are available, the temporary permission stream is stopped immediately.
3. `enumerateDevices()` must expose a matching Zone Vibe 100 `audioinput` and `audiooutput`.
4. The UI shows the selected input and output names.
5. Only then is **Start realtime listening** enabled.

The device check does not record, retain audio, or play sound. Browser output enumeration proves visibility, not physical playback. A future speaker test remains a separate, explicitly consented action and is outside this release.

A `devicechange`, ended microphone track, missing selected device, or WebSocket disconnect immediately invalidates the check and stops all microphone tracks. Reconnection never restarts capture automatically. The user must check devices again and explicitly resume.

## Realtime Studio UI

### Visual system

- Product style: OLED dark developer tool.
- Background: deep navy/black surfaces with restrained borders.
- State colors: VAD teal, endpoint amber, ASR cyan/blue, correction violet, error red.
- Every state includes text and an icon; color is never the only signal.
- Body text is at least 16 px on mobile, interactive targets are at least 44 by 44 px, keyboard focus is visible, and contrast targets WCAG AA or better.
- Desktop layout uses a main waveform/transcript column plus a pipeline-status rail.
- Mobile places the waveform and transcript first and collapses advanced pipeline details below them without horizontal scrolling.

### Motion

The copied React Bits `Waves` component supplies a low-contrast ambient state layer. Its source and license notice are preserved as required by the upstream repository. It never substitutes for the actual microphone waveform.

The actual waveform is rendered from Web Audio samples. Motion communicates state:

- listening: quiet, low-amplitude ambient wave;
- speech: live waveform and teal VAD emphasis;
- endpoint candidate: amber countdown;
- ASR processing: blue activity pulse;
- correction: violet text revision shimmer;
- error: motion stops and a recovery message receives focus.

Micro-interactions use 150–300 ms transitions. `prefers-reduced-motion: reduce` disables ambient waves, shimmer, and nonessential transitions while retaining text, numeric progress, and state changes.

### Information hierarchy

1. Hardware readiness and one primary start/stop action.
2. Actual microphone waveform and current listening state.
3. Stable, revisable, and partial transcript rows.
4. VAD, endpoint, ASR queue, and correction status cards.
5. Actual GPU/CPU device, queue depth, latency, and dropped-frame diagnostics.

## Backpressure and recovery

- Partial queue pressure discards only superseded pending partial jobs.
- Final ASR jobs are never silently dropped.
- Near-capacity queues emit `pipeline.warning` and show amber backpressure.
- A full final queue completes the current utterance, stops accepting new audio, stops client capture, and requires an explicit resume after recovery.
- ASR worker failure retains bounded final audio and retries once after readiness. Partial work may be abandoned.
- Correction failure or timeout preserves final ASR text and allows subsequent utterances.
- WebSocket loss stops capture immediately; missing audio is never fabricated or replayed.
- Worker and queue state are visible in capabilities, health details, and realtime events.

## Privacy and persistence

- Raw audio lives only in bounded memory for the active utterance.
- Raw audio is released after final ASR or terminal failure.
- No recording, audio feature, transcript database, model weight, log, runtime file, or session-private state is committed to Git.
- Transcripts remain in bounded in-memory session history for UI replay. Persistent transcript storage is excluded.
- Logs contain identifiers, stage names, timings, queue depth, and typed errors, but never PCM bytes or full transcript text by default.

## Configuration

New settings remain under `AGENT_SPEAK_*` and receive validation and `.env.example` documentation. The design requires configurable values for:

- realtime frame size and maximum input rate;
- VAD threshold, pre-roll, and minimum speech;
- partial interval;
- endpoint baseline and hard maximum;
- endpoint decision deadline, defaulting to 250 ms;
- utterance duration and ring-buffer size;
- partial, final, and correction queue limits;
- worker deadlines and retry count;
- ASR worker URL and correction worker URL on the internal network;
- correction model path, context size, and protected-token validation;
- expected device-name pattern, defaulting to Zone Vibe 100.

Defaults implement the approved 20 ms frame, 300 ms pre-roll, 250 ms minimum speech, 800 ms partial interval, 900 ms endpoint baseline, 1,800 ms hard endpoint, and 30-second utterance bound.

## Testing strategy

### Unit tests

- VAD and endpoint state transitions use synthetic PCM and a fake monotonic clock.
- Tests cover 900 ms candidates, continuation extension, speech resumption, and the 1,800 ms hard boundary.
- Scheduler tests cover stale partial replacement, final priority, bounded queues, and shutdown.
- Transcript tests cover stable-prefix reconciliation and stale generation rejection.
- Revision tests prove only the newest prior sentence can change.
- Correction guards cover names, numbers, English, code, edit bounds, invalid JSON, and timeout.

### Contract and integration tests

- WebSocket tests cover control JSON, binary PCM framing, event order, typed close errors, disconnect cleanup, and bounded event replay.
- Existing REST, MCP, session, `/`, and `/codex` tests remain green.
- Provider contract tests prove ASR and correction can be replaced without transport changes.
- Worker health and failure injection tests cover retry and degraded behavior.

### Frontend tests

- Vitest covers transcript reconciliation, state reducers, device gating, and reconnect behavior.
- AudioWorklet tests cover PCM conversion, frame bounds, and shutdown.
- Browser tests cover permission denial, missing input/output, `devicechange`, disabled states, keyboard navigation, reduced motion, and 375/768/1024/1440 px layouts.
- The start control cannot become enabled until both Zone Vibe 100 endpoints are visible.

### Container acceptance

- CPU mode completes VAD, endpoint, ASR, correction, and UI event flow without NVIDIA.
- GPU mode proves both workers see the actual GPU and completes real Faster-Whisper plus Qwen correction without CUDA-library errors.
- A representative Mandarin and Mandarin/English corpus measures latency and correction regressions.
- A 30-minute continuous session covers multiple utterances, natural pauses, reconnect refusal, bounded memory, and zero silent final-utterance loss.

## Acceptance targets

- Local waveform feedback: under 100 ms.
- `vad.speech_started`: approximately 200 ms after speech onset.
- First partial transcript after model warmup: within 1.5 seconds.
- Endpoint candidate: `900 ms ± 1 frame` of silence.
- Hard endpoint: `1,800 ms ± 1 frame` of silence.
- Final ASR plus correction: target within 2 seconds after endpoint on the verified RTX 2080 Ti host.
- Continuous listening resumes after every completed utterance without another start click.
- Every transcript update carries an `utterance_id`; partial text from different utterances cannot mix.
- No automatic microphone start, speaker playback, Agent call, or Codex injection.

Latency targets are acceptance goals, not universal hardware guarantees. The UI reports measured values and degraded mode rather than misrepresenting slower CPU hosts as meeting GPU targets.

## Source choices

- React Bits repository and `Waves` component: <https://github.com/DavidHDev/react-bits>
- Qwen2.5 1.5B Instruct model: <https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct>
- Official Qwen GGUF quantization: <https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF>
- llama.cpp CUDA/OpenAI-compatible server: <https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>
- OpenAI public delta/completed transcription model for UX comparison only: <https://developers.openai.com/api/docs/guides/realtime-transcription>
- OpenAI public server/semantic VAD concepts for architecture comparison only: <https://developers.openai.com/api/docs/guides/realtime-vad>

OpenAI services are not runtime dependencies of this local design.
