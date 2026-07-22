# Multi-Model Realtime ASR and Generic Audio Device Design

Date: 2026-07-22
Status: Approved design; implementation pending

## Goal

Improve Taiwanese Mandarin and Mandarin-English code-switching recognition while
keeping the realtime studio local, explicit, and resource-bounded. The studio
will support three selectable ASR models, an optional correction stage, generic
system-default audio-device detection, one-command model preparation, and a more
audio-like Live Audio visualization.

This design preserves `/api/v1`, provider boundaries, session immutability, the
external Agent/MCP contract, and the rule that microphone capture or speaker
playback requires explicit user action.

## Decisions

- ASR choices are Faster-Whisper small, Breeze ASR 25, and Qwen3-ASR 1.7B.
- Qwen3-ASR 1.7B is the default.
- Correction choices are Qwen2.5 Correction and Disabled / Raw ASR.
- One ASR model is resident at a time. Selection initiates an automatic stop,
  model reload, new session, and resume; there is no Submit button.
- Completed transcripts and graph nodes survive a model switch. Unfinished
  partial text is discarded. Each completed utterance records its ASR model.
- Device readiness uses the current browser/system default input and output;
  no brand or Bluetooth-name heuristic is used.
- `./run.sh --models` performs explicit, idempotent model downloads. Normal
  build/up paths verify models but never begin a multi-gigabyte download.
- Live Audio uses layered signal ribbons driven by the real microphone envelope.

## Model scope and sources

| Public model ID | Source and pinned revision | Runtime | Purpose |
| --- | --- | --- | --- |
| `faster-whisper-small` | `Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120` | CTranslate2 / Faster-Whisper | Compact compatibility option |
| `breeze-asr-25` | `MediaTek-Research/Breeze-ASR-25@cffe7ccb404d025296a00758d0a33468bec3a9d0` | Transformers Whisper | Taiwanese Mandarin and Mandarin-English code-switching |
| `qwen3-asr-1.7b` | `Qwen/Qwen3-ASR-1.7B@7278e1e70fe206f11671096ffdd38061171dd6e5` | Official `qwen-asr` Transformers backend | Default multilingual/noisy-audio option |
| `qwen2.5-correction` | `Qwen/Qwen2.5-1.5B-Instruct-GGUF@91cad51170dc346986eccefdc2dd33a9da36ead9` | llama.cpp | Existing bounded endpoint/correction worker |
| Piper voice | Piper catalog name `zh_CN-huayan-medium` | Piper | Existing TTS voice; included in unified model preparation |

These revisions are the reproducibility baseline captured on 2026-07-22. A
future revision upgrade is an explicit manifest and regression change, not an
implicit consequence of running the downloader later.

Breeze ASR 26 is deliberately out of scope. Its official model card identifies
it as a Taiwanese Hokkien (Taigi) ASR model, not a direct Mandarin/code-switching
upgrade to Breeze ASR 25. It can be added later as a separate language-specific
provider if Taigi recognition becomes a requirement.

Primary references:

- [Breeze ASR 25 model card](https://huggingface.co/MediaTek-Research/Breeze-ASR-25)
- [Breeze ASR 26 model card](https://huggingface.co/MediaTek-Research/Breeze-ASR-26)
- [Qwen3-ASR official repository](https://github.com/QwenLM/Qwen3-ASR)
- [Qwen3-ASR 1.7B model card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)

The first implementation uses Qwen's Transformers backend, not vLLM. This fits
the existing bounded-WAV/rolling-partial queue with fewer CUDA and container
compatibility risks. A later vLLM migration requires its own measured design.

## Audio device gate

All `Zone Vibe 100` constants, documentation, presentation strings, and tests are
removed. Device checking remains an explicit browser action:

1. Request temporary microphone permission with `getUserMedia`.
2. Enumerate media devices after labels become available.
3. Select `deviceId === "default"` for `audioinput` and `audiooutput` when
   present; otherwise select the first entry of that kind with a non-empty label.
4. Enter Ready only when both are present and display their actual labels.
5. Stop the temporary permission stream immediately.
6. Start capture using the frozen input device ID.
7. On `devicechange`, stop any active stream and revoke Ready until rechecked.

This proves browser visibility, not Bluetooth transport, shared physical-device
identity, or successful playback. The realtime page performs no speaker output.

## Session model contract

Session creation adds two optional, immutable values:

```text
asr_model = faster-whisper-small | breeze-asr-25 | qwen3-asr-1.7b
correction_model = qwen2.5-correction | disabled
```

The defaults are `qwen3-asr-1.7b` and `qwen2.5-correction`. Both values are
returned in `SessionSummary`, emitted in `session.created`, and copied into all
realtime jobs and completed utterance metadata. No endpoint mutates an existing
session.

Speech language remains a separate frozen dimension. Presentation locale,
speech language, ASR model, correction policy, and TTS voice must not overwrite
one another.

Standalone `/api/v1/audio/asr` and MCP `listen_once` use the configured active or
default ASR model. They do not inherit browser presentation locale and cannot
silently request a model switch while a realtime lease is active.

## Model-control API

The additive public contract is:

- `GET /api/v1/models`: catalog entries, download/readiness state, active and
  requested model IDs, device, progress stage, and bounded error details.
- `PUT /api/v1/models/active`: idempotently request an ASR model and correction
  policy. It returns ready state immediately or a loading operation that the UI
  polls through `GET /api/v1/models`.

The state machine is:

```text
stopping → unloading → loading → warming → ready → resuming
                              ↘ failed → rollback → ready|failed
```

The ASR worker exposes an internal model-manager boundary. It owns provider
construction, unload, CUDA cache cleanup, warm-up, last-known-ready rollback,
and a single active lease. Gateway API code maps this state without owning model
internals or Docker control.

An active realtime stream holds a lease for its frozen ASR model. A conflicting
activation request receives HTTP 409. The first-party UI always stops and waits
for stream closure before activation. The Gateway never mounts the Docker socket
and never starts/stops containers in response to a browser request.

## Provider registry and resource policy

The ASR worker implements a registry whose entries share the current ASR
protocol but may use different libraries. Exactly one ASR provider is loaded at
a time. Switching unloads the old provider before constructing the new one, then
runs a bounded warm-up. The NVIDIA path uses FP16 on the current RTX 2080 Ti;
CPU remains supported but is explicitly labeled slow for the larger models.

The ASR runtime is a dedicated Docker target containing PyTorch, Transformers,
`qwen-asr`, CTranslate2, and their audio dependencies. Gateway, MCP, and test
images do not acquire the large ASR runtime dependency set.

The Qwen2.5 correction worker remains a separate llama.cpp service. Selecting
`disabled` bypasses correction for that session and preserves final ASR text;
endpoint detection continues to run. The correction worker need not be unloaded
to toggle this policy.

## Model preparation

`./run.sh --models` builds a small downloader target and populates the private
model volume from a fixed manifest. It downloads only inference artifacts. For
Breeze ASR 25 this excludes optimizer state and duplicate `.pt` checkpoints.

The operation is:

1. Resolve the configured model root and reject paths outside it.
2. Determine missing artifacts and their required free-space allowance.
3. Require a safety reserve beyond estimated downloads and temporary files.
4. Download into model-specific `.partial` directories.
5. Verify required files, non-zero sizes, and the pinned repository revision.
6. Atomically rename a verified directory into its final location.
7. Leave verified cached models untouched.
8. On failure, remove only the operation's incomplete `.partial` path and report
   the exact failed model; never prune Docker or unrelated user files.

`./run.sh --build` and `--up` are verify-only. If models are missing, they list
the model IDs and instruct the operator to run `./run.sh --models`.

The design snapshot has 37GB free on `/dev/nvme0n1p2`. Official inference
weights are roughly 0.5GB for Faster-Whisper small, 3.1GB for the necessary
Breeze safetensors set, 4.7GB for Qwen3-ASR 1.7B, 1.1GB for correction, and
about 61MB for Piper. Runtime images and download/build transients still require
preflight; implementation must stop rather than auto-delete when the reserve is
insufficient.

Model weights, caches, `.partial` paths, runtime state, and download logs remain
ignored and must never be committed.

## Realtime UI behavior

The ACTIVE MODELS card contains two accessible, localized, minimum-44px selects:

- ASR: Qwen3-ASR 1.7B, Breeze ASR 25, Faster-Whisper small.
- Correction: Qwen2.5 Correction, Disabled / Raw ASR.

There is no Submit button. When idle, a selection activates immediately. When
Listening, the UI performs:

1. Stop and await stream closure.
2. Drop only unfinished partial text.
3. Request activation and render each loading stage plus progress/error text in
   both the card and an accessible live region.
4. Disable both selectors while switching.
5. When ready, create a new session with frozen language/model choices.
6. Resume only if the device gate is still valid.

If a device change occurs during model loading, the UI does not resume. If load
or warm-up fails, the worker attempts last-model rollback, the UI reports the
error, and Listening remains stopped even if rollback succeeds.

Completed transcript rows and graph nodes remain visible across model sessions.
Every completed utterance stores its ASR model ID. The transcript may show a
compact model badge; graph hover displays the model name with escaped text.

Downloaded/readiness state comes from `/api/v1/models`. Missing models appear as
Unavailable with a localized `./run.sh --models` instruction and cannot be
selected.

## Live Audio visualization

The current polygonal line chart becomes two layered, smoothed signal ribbons.
They are derived from the actual microphone envelope, not an unrelated ambient
animation:

- resample and smooth recent envelope points;
- draw two phase-offset bezier ribbons around a stable center line;
- map energy to amplitude and restrained glow intensity;
- use an ice-blue to violet gradient consistent with the existing visual system;
- retain HiDPI canvas sizing and responsive bounds;
- use a quiet idle form without fabricating speech energy;
- reduce or remove interpolation/glow motion under `prefers-reduced-motion` while
  preserving the semantic state label.

Text and state indicators remain the authoritative status channel.

## Failure handling

- Unknown model IDs use stable validation errors.
- Missing artifacts return unavailable state and the explicit preparation command.
- Lease conflicts return HTTP 409 without unloading the active model.
- Model load, warm-up, OOM, CUDA, or provider errors are bounded and do not leak
  filesystem paths or stack traces through the public API.
- Rollback failure leaves the worker unavailable and requires operator action; it
  must not claim the previous model is active.
- Rapid selector changes are prevented while an activation is in progress.
- A device invalidation always takes precedence over automatic resume.
- Correction failure retains existing raw-final-ASR fallbacks; disabled correction
  intentionally follows the same raw-text result without reporting a failure.
- Existing transcript nodes never change model attribution after completion.

## Test and acceptance plan

Implementation follows test-driven development. Hardware-free regressions cover:

- generic default input/output selection, fallback, permission denial, and
  `devicechange` invalidation;
- absence of `Zone Vibe 100` from README, active source, settings, and localized
  presentation catalogs;
- model manifest, disk preflight, cached skip, `.partial` cleanup, allow-listed
  Breeze files, and exact required-file validation;
- all three provider adapters and speech-language mappings;
- worker unload/load, progress, rollback, lease conflict, and public HTTP 409;
- session model defaults, immutability, serialization, and realtime propagation;
- unchanged standalone/MCP boundaries;
- direct selectors, loading/error states, device-invalidated no-resume behavior;
- completed transcript/graph preservation and immutable model metadata;
- layered ribbons driven by supplied envelope data, HiDPI resize, and reduced
  motion;
- complete `./run.sh --test`, CPU image build, and NVIDIA image build.

Integration acceptance downloads the pinned artifacts, starts the production
stack, and sends bounded synthetic or public WAV fixtures through each ASR model.
It verifies non-empty text, provider identity, model switch/rollback behavior,
correction enabled/disabled behavior, and service health. It does not use the
microphone or play audio.

A real headset smoke test remains separate and occurs only after fresh explicit
user consent. Browser enumeration alone is never reported as physical recording
or playback proof.

## Out of scope

- Breeze ASR 26 / Taigi recognition.
- vLLM deployment in the first implementation.
- Loading all ASR models concurrently.
- Mid-utterance or in-place session model mutation.
- Automatic disk cleanup or Docker pruning.
- TTS voice switching.
- Agent/Codex session injection.
- Automatic microphone capture or physical speaker playback.
