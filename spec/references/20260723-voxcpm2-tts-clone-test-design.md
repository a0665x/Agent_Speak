# VoxCPM2 TTS Clone Test Design

Date: 2026-07-23

## Goal

Add a local `/tts_clone_test` experience that lets a user record one
ephemeral voice reference, synthesize text with VoxCPM2 through vLLM-Omni,
and explicitly play the generated speech. The first version is a zero-shot
cloning test, not LoRA training and not a persistent voice-profile system.

The feature preserves the existing `/api/v1` provider boundary, never grants
the browser Docker control, and never starts microphone capture or physical
playback without a direct user action.

## Upstream basis

- VoxCPM2 is the selected model: `openbmb/VoxCPM2`, pinned to an explicit
  revision by the project model manifest.
- vLLM-Omni is the serving framework. Its supported-model catalog lists
  VoxCPM2 on NVIDIA GPU, and its speech API accepts `ref_audio` for zero-shot
  cloning.
- VoxCPM2 documents natural-language control instructions, voice cloning,
  48 kHz output, approximately 8 GB inference VRAM, and 30-language
  synthesis.
- Literal `[laugh]`, `[cough]`, `[snicker]`, and `[sigh]` event syntax is not
  documented as a VoxCPM2 native contract. The UI therefore exposes friendly
  style cues and compiles them into natural-language control text.

Primary references:

- <https://github.com/OpenBMB/VoxCPM>
- <https://docs.vllm.ai/projects/vllm-omni/en/latest/models/supported_models/>
- <https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/examples/online_serving/text_to_speech/>
- <https://docs.vllm.ai/projects/vllm-omni/en/latest/getting_started/installation/gpu/>

## Scope

Included:

- A homepage navigation card and localized `/tts_clone_test` page.
- Generic browser microphone and speaker discovery.
- One replaceable 5–30 second reference recording in browser memory.
- Reference quality validation without persistence.
- VoxCPM2 default-voice synthesis and optional zero-shot cloning.
- Friendly style-cue controls translated to natural-language instructions.
- Separate Generate and Play actions.
- A state-reactive 2D gradient Voice Orb.
- GPU-mode, worker, model, device, recording, generation, and playback status.
- A separate vLLM-Omni TTS worker and explicit CLI GPU-mode switching.
- Privacy-preserving structured diagnostics.

Excluded:

- LoRA or full fine-tuning.
- Multiple reference clips or persistent voice profiles.
- Reference audio upload from disk.
- Literal non-verbal token guarantees.
- Automatic Docker control from the browser or Gateway.
- Automatic microphone capture, automatic playback, or autoplay.
- Simultaneous resident ASR, correction, and VoxCPM2 models on a constrained
  single GPU.

## Hardware and runtime constraint

The development host has one RTX 2080 Ti with 11 GB VRAM. The existing ASR,
correction, display, and desktop workload uses enough VRAM that the
approximately 8 GB VoxCPM2 runtime cannot safely coexist with the complete ASR
stack.

The deployment therefore uses mutually exclusive GPU modes:

```text
ASR mode
  Gateway + ASR worker + correction worker
  TTS clone worker stopped

TTS mode
  Gateway + VoxCPM2/vLLM-Omni worker
  ASR worker + correction worker stopped
```

The Gateway remains available in both modes so the homepage, API status,
Swagger, and active demo page continue to work. APIs whose worker is not active
return a bounded, explicit `wrong_gpu_mode` or `provider_unavailable` response.

The browser and Gateway never receive access to the Docker socket. Operators
switch modes through explicit host CLI commands:

```sh
./run.sh --models
./run.sh --asr-up
./run.sh --tts-up
./run.sh --status
./run.sh --logs tts-worker
```

`--models` downloads and verifies all pinned models. `--asr-up` restores the
current ASR stack. `--tts-up` stops GPU ASR/correction services before starting
the TTS worker. `--status` reports `gpu_mode=asr|tts`, worker/model state,
accelerator, and audio-device availability.

## Component boundaries

### TTS worker

A dedicated Python 3.12 image runs vLLM-Omni and VoxCPM2. It is reachable only
on the Compose network and exposes health plus the OpenAI-compatible speech
endpoint. It does not receive host audio-device access.

The worker owns model loading and GPU inference. It does not persist reference
or generated audio and does not expose a host port.

### Gateway adapter

The Gateway owns the public `/api/v1` contract and a small VoxCPM2 adapter. It:

- reads worker status with bounded timeouts;
- validates text and WAV limits before forwarding;
- compiles allowlisted style cues into natural-language control text;
- converts the validated reference to the worker's `ref_audio` representation;
- normalizes worker, timeout, OOM, and wrong-mode failures;
- validates the returned audio before sending it to the browser;
- emits privacy-safe diagnostic events.

The existing Piper provider and `/api/v1/tts/synthesize` contract remain
unchanged. Clone-test behavior is additive and provider-specific.

### Browser application

A dedicated React/Vite entry follows the existing ASR page's visual tokens,
localization, device-gate patterns, responsive behavior, and accessibility
rules. It owns:

- browser audio-device discovery;
- explicit recording controls;
- the single in-memory reference WAV;
- local real-time amplitude visualization;
- synthesis request state;
- the generated audio Blob and Blob URL;
- explicit browser playback and output-amplitude visualization.

## Public API

### `GET /api/v1/tts-clone/status`

Returns:

- selected GPU mode;
- accelerator and GPU availability;
- worker state: `stopped`, `starting`, `loading`, `ready`, or `failed`;
- model identifier and readiness;
- bounded recovery code and operator hint when unavailable.

It never starts or switches a service.

### `POST /api/v1/tts-clone/reference/validate`

Accepts one raw PCM WAV with the existing maximum byte limit and a 5–30 second
duration contract.

Returns duration, RMS/input level, voiced ratio, and a bounded quality result:
`good`, `too_quiet`, `too_little_voice`, `too_short`, or `too_long`. It does
not write the WAV to disk.

### `POST /api/v1/tts-clone/synthesize`

Accepts bounded multipart fields:

- `text`;
- an allowlisted list of style-cue identifiers;
- `use_clone`;
- one reference PCM WAV when `use_clone=true`.

It rejects a missing or invalid reference when cloning is enabled. A successful
response is validated `audio/wav`, streamed directly to the browser with
correlation and model headers. It does not create a persistent artifact.

## Privacy and lifecycle

The reference exists only as an in-memory browser object and the bounded
request being processed. Re-recording revokes the previous Blob URL and
replaces the reference. Page unload/reload revokes all Blob URLs and clears the
reference plus generated audio.

The Gateway and worker do not write:

- reference audio;
- generated audio;
- voice embeddings;
- transcripts;
- synthesis text;
- browser device labels.

Logs may include request ID, anonymized session reference, model, mode, stage,
duration, status, latency, error code, and exception class. They must not
include request bodies, text, audio, credentials, raw session identifiers,
device labels, or exception messages.

## User interface

### Navigation and localization

The homepage receives a third destination card for `TTS Clone Test`.
`/tts_clone_test` supports the existing `en`, `zh-TW`, `ja`, and `ko` locale
resolution and defaults to English.

### Persistent readiness

The page continuously presents:

- microphone availability;
- speaker availability;
- CUDA availability;
- GPU mode;
- vLLM-Omni worker state;
- VoxCPM2 model state;
- whether a valid current reference exists.

Controls are disabled with a specific explanation when their prerequisites are
not satisfied. CPU-only systems remain browsable but cannot record for cloning,
generate, or play through this GPU feature.

### Two freely switchable modes

`Voice Clone` and `TTS Play` are tabs, not a forced wizard. Switching tabs does
not clear a valid current reference.

#### Voice Clone

- The user explicitly starts and stops recording.
- The recommended target is 10–15 seconds; accepted duration is 5–30 seconds.
- The page presents elapsed duration, VAD/voice ratio, input level, and quality.
- A valid new reference replaces the previous reference.
- The page describes zero-shot reference conditioning and never calls this
  operation model training.

#### TTS Play

- The user enters bounded text.
- The user may select friendly style cues such as Light laugh, Snicker, Sigh,
  Cough, Warm, Cheerful, Soft, and Faster.
- Cues are global best-effort controls in the first version. They map to
  allowlisted natural-language VoxCPM2 instructions and are not sent as literal
  bracket tokens.
- `Use current cloned reference` is enabled only when a valid reference exists.
- When disabled, VoxCPM2 uses its default voice behavior.
- Generate produces an in-memory audio Blob and never starts playback.
- Play becomes enabled only after successful generation. Each Play click is the
  user's explicit physical-playback action.

### Voice Orb

One 2D gradient Voice Orb provides consistent state feedback:

- recording: reacts to real microphone amplitude and VAD;
- validation: settles into a bounded quality-check pulse;
- queued/loading/generating: uses distinct deterministic phase motion;
- audio ready: becomes bright and stable;
- playing: reacts to actual output amplitude from the browser audio graph;
- complete: returns smoothly to idle;
- unavailable/error: becomes low-luminance with an adjacent textual status.

The Orb is never the only status indicator. Text, icons, and live regions carry
the same state. `prefers-reduced-motion` removes large movement and preserves
only restrained color/opacity state changes.

## Error and recovery contract

The UI and API distinguish:

- `wrong_gpu_mode`: run `./run.sh --tts-up`;
- `gpu_unavailable`: use a supported NVIDIA GPU;
- `worker_starting` / `model_loading`: wait while status continues polling;
- `provider_unavailable`: inspect `./run.sh --logs tts-worker`;
- `microphone_unavailable`: connect or grant access to an input device;
- `speaker_unavailable`: connect or select an output device;
- reference duration, silence, low-level, or low-voice validation errors;
- `tts_timeout`;
- `gpu_out_of_memory`;
- malformed or oversized worker audio;
- browser playback rejection.

Every error identifies a recovery action. A failed generation preserves the
text and reference so the user can retry. It never auto-retries playback.

## Testing and acceptance

All production behavior is test-first.

Hardware-free coverage includes:

- pinned VoxCPM2 manifest, atomic preparation, and disk reserve;
- Compose profiles and `run.sh` ASR/TTS switching;
- no Docker socket mount and no public TTS-worker port;
- worker adapter request shape, status mapping, timeouts, OOM normalization,
  output validation, and log redaction;
- reference WAV bounds and quality results;
- proof that validation and synthesis create no persistent audio artifacts;
- localized homepage and clone-test routes;
- device gate, two tabs, one-reference replacement, clone toggle, style-cue
  mapping, Generate/Play separation, Blob cleanup, and Voice Orb states;
- CPU/wrong-mode states without GPU access;
- reduced-motion and keyboard/accessibility behavior.

Runtime acceptance uses a synthetic reference WAV and synthetic text to prove
that VoxCPM2 returns a valid 48 kHz WAV through the public Gateway. This smoke
test does not activate the microphone or physical speaker. Final real-device
acceptance requires the user to click Record and Play.

The complete existing `./run.sh --test` suite must remain green.

## Operational notes

The current host had 40 GB free before implementation. Model and image
preparation must still run the existing storage preflight and preserve the
configured 8 GB safety reserve. If pinned weights plus temporary download and
container layers cannot fit, the command must stop before a partial model is
installed.

No model weights, recordings, generated WAV files, voice features, logs,
runtime state, database, `.env`, or credentials may enter Git.
