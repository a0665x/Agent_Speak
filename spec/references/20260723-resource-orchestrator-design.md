# Extensible GPU Resource Orchestrator Design

Date: 2026-07-23

## Goal

Add one-click resource recovery to the ASR Realtime and TTS Clone Test pages
without making ASR/TTS mutual exclusion a permanent architecture constraint.
The current 11 GB GPU continues to use exclusive model residency, while future
high-VRAM and multi-GPU hosts can keep ASR, correction, Agent, and TTS workers
resident together.

The resource control plane must remain separate from audio and inference data.
It must not grant the public Gateway a Docker socket or accept arbitrary host
commands.

## Design principles

1. Mutual exclusion is a resource policy, not a provider contract.
2. The Gateway remains available while inference workers reconcile.
3. Desired workload state and observed worker state are distinct.
4. UI controls request outcomes; they do not issue Docker commands.
5. Operations are serialized, observable, bounded, and idempotent.
6. Microphone capture and speaker playback always remain explicit user actions.
7. The future Agent stage uses a provider boundary and never silently falls
   back to the development echo.

## Architecture

### Stable Gateway

The Gateway remains the only public HTTP boundary and is not recreated during
normal ASR/TTS resource reconciliation. It exposes a typed `/api/v1/resources`
control contract, reads operation state from the Resource Orchestrator, and
continues serving both Web UIs while workers stop, start, or warm.

The current startup-time `gpu_mode=asr|tts` becomes compatibility input during
migration, not the long-term source of truth. Runtime readiness is derived from
the orchestrator's desired workloads and observed worker health.

### Host Resource Orchestrator

A host-owned Resource Orchestrator is started and stopped by `run.sh`. The
Gateway communicates with it through a Unix domain socket under ignored
`runtime/resource-control/`. The Gateway does not receive the Docker socket,
Docker CLI, Compose project files, or permission to run arbitrary subprocesses.

The orchestrator owns:

- GPU inventory and usable-memory observations;
- configured resource policy and worker placement;
- desired and observed workload sets;
- serialized lifecycle operations;
- fixed worker start, stop, health, and warm-up adapters;
- atomic operation state stored under ignored runtime state;
- bounded timeout, rollback, and recovery hints.

Only allowlisted workload identifiers and actions are accepted. The initial
workloads are `asr`, `correction`, and `tts`; `agent` is reserved for the future
Agent provider. Lifecycle adapters invoke fixed project operations and never
interpolate request data into shell commands.

### Independent workers

ASR, correction, Agent, and TTS remain independent provider workers. A worker
can be resident, warming, ready, draining, stopped, or failed. The orchestrator
may stop and start workers on a constrained GPU or leave them resident on a
capable host.

The Gateway talks only to ready providers. A model selector remains present
while its worker is unavailable; its options come from the pinned model
manifest and its lifecycle row explains why activation is unavailable.

## Resource policies and profiles

The selected policy defines placement and eviction behavior:

| Policy | Intended host | Behavior |
| --- | --- | --- |
| `auto` | Default | Select the safest supported policy from GPU inventory and configured model budgets. |
| `exclusive` | Current 11 GB-class GPU | ASR/correction and TTS are mutually exclusive residency groups. |
| `concurrent` | High-VRAM GPU | ASR, correction, and TTS may remain resident together. |
| `multi_gpu` | Multiple configured GPUs | Place workload groups on explicitly assigned devices. |

Profiles describe desired workload outcomes:

| Profile | Desired workloads |
| --- | --- |
| `asr_only` | `asr`, `correction` |
| `tts_only` | `tts` |
| `full_pipeline` | `asr`, `correction`, `agent`, `tts` |

`auto` is conservative. It may select concurrent residency only when configured
budgets, detected usable memory, and worker preflight all permit it. A failed
concurrent preflight does not overcommit the GPU; it reports a bounded failure
or applies an explicitly configured fallback. It never silently changes a
user-selected policy.

The current host initially resolves `auto` to `exclusive`. Moving to a
high-VRAM host can resolve `auto` to `concurrent`, or the operator can explicitly
configure `concurrent`. No UI or provider contract changes are required.

## Public API

### `GET /api/v1/resources`

Returns:

- selected policy and resolved policy;
- GPU inventory summary without device serials or private labels;
- desired and observed workloads;
- profile;
- current operation, if any;
- each workload's lifecycle, model, device class, readiness, and bounded error;
- supported profiles and policies.

### `POST /api/v1/resources/reconcile`

Accepts one allowlisted `profile` or an allowlisted workload set. The first UI
release sends only a profile:

```json
{"profile": "asr_only"}
```

or:

```json
{"profile": "tts_only"}
```

The response is `202 Accepted` with an operation ID. Repeating the same desired
state is idempotent and returns the active or completed equivalent operation.

### `POST /api/v1/resources/{workload}/reset`

Restarts one allowlisted workload within the current desired profile. It is for
recovery after a worker failure, not for changing profiles. Resetting a workload
that is not desired returns a stable conflict with a recovery hint.

### `GET /api/v1/resource-operations/{operation_id}`

Returns the operation state:

`queued → draining → releasing → starting → warming → ready`

Terminal states are `ready`, `failed`, `rolled_back`, and `cancelled`.
Responses include timestamps, workload lifecycle summaries, stable error codes,
and bounded operator hints. They never include commands, audio, transcripts,
prompt text, credentials, raw exception messages, or private filesystem paths.

## Reconciliation and failure behavior

Operations are protected by a single host lock. A second incompatible request
receives the active operation instead of starting a competing lifecycle change.

For `exclusive` ASR-to-TTS reconciliation:

1. mark ASR/correction as draining;
2. reject new ASR sessions and allow a short bounded drain window;
3. stop ASR/correction workers;
4. verify their GPU allocations are released;
5. start TTS;
6. wait for model and synthetic internal health readiness;
7. publish `ready`.

The reverse flow applies to TTS-to-ASR. A failure records the failed stage and
attempts one rollback to the last known ready profile. If rollback also fails,
the Gateway stays available and reports both workloads unavailable with explicit
operator recovery commands.

For `concurrent`, reconciliation starts only missing workloads and does not
evict healthy desired workers. A workload reset affects only that worker unless
its provider dependency requires a bounded dependent restart.

The Gateway and UI tolerate temporary worker connection failures. They do not
interpret a transient health failure as a missing model catalog.

## Future Agent pipeline

The future full pipeline is:

```text
Browser audio
  → VAD / endpoint
  → ASR worker
  → Agent provider
  → TTS worker
  → explicit browser playback
```

Each stage uses bounded queues, correlation IDs, cancellation, timeouts, and
backpressure. ASR final text is the Agent input; partial text is never submitted
as a completed turn. The Agent provider can target an external Codex/LLM host or
a local model worker. The existing development echo remains visibly labelled
and cannot satisfy `full_pipeline` readiness.

TTS synthesis and playback remain separate. A successful Agent or TTS result
does not grant speaker consent.

## Web UI behavior

Both pages receive a secondary, touch-sized reset control near runtime status:

- ASR Realtime: **Reset ASR resources**
- TTS Clone Test: **Reset TTS resources**

The labels and all operation states are complete in English, Traditional
Chinese, Japanese, and Korean.

Pressing the control:

1. shows a confirmation if a session, recording, generation, or playback is
   active;
2. stops the page-owned activity after confirmation;
3. requests `asr_only` or `tts_only`;
4. disables repeated reset and model-switch actions;
5. renders operation stages with an accessible live status;
6. polls through temporary Gateway/worker failures with bounded backoff;
7. refreshes capabilities, model catalog, and runtime status at `ready`.

Completed ASR transcripts and graph nodes remain visible, but the old live
session is not resumed automatically. TTS reference audio stays browser-local
when the page remains loaded; no capture or playback starts automatically.

ASR selectors never disappear. While ASR is not ready, the pinned choices stay
visible and disabled with the current lifecycle. After readiness, selected and
active rows are refreshed from one catalog snapshot.

## Security and privacy

- Gateway has no Docker socket and no arbitrary command endpoint.
- The orchestrator Unix socket is stored in an ignored, permission-restricted
  runtime directory.
- Requests accept enums and bounded identifiers only.
- Lifecycle adapters use argument arrays and fixed actions without a shell.
- Operation state and logs exclude audio, transcripts, synthesis text, device
  labels, credentials, raw session IDs, exception strings, and private paths.
- Public resource endpoints remain loopback-only under the existing deployment
  contract. Remote deployments require the existing trusted HTTPS/auth layer.
- Resource operations never request browser media permission and never play
  audio.

## Configuration

Untracked environment configuration will support:

- `AGENT_SPEAK_RESOURCE_POLICY=auto|exclusive|concurrent|multi_gpu`;
- per-workload GPU assignment for `multi_gpu`;
- conservative per-model memory budgets;
- drain, startup, warm-up, and rollback timeouts.

Defaults preserve current behavior: `auto` on the present 11 GB-class host
resolves to `exclusive`.

## Migration

1. Add the host orchestrator, Unix-socket protocol, atomic state, and `run.sh`
   lifecycle without changing existing `--asr-up` or `--tts-up` behavior.
2. Add Gateway resource APIs and derive readiness dynamically.
3. Keep the Gateway stable while worker adapters reconcile the existing
   exclusive groups.
4. Add both UI reset controls and persistent ASR catalog presentation.
5. Add `concurrent` and `multi_gpu` placement after exclusive real-hardware
   acceptance.
6. Add the `agent` workload and `full_pipeline` only when a real Agent provider
   exists.

Existing operator commands remain supported as recovery and automation entry
points.

## Testing and acceptance

Hardware-free tests cover:

- policy/profile validation and deterministic planning;
- command allowlists and rejection of arbitrary values;
- Unix-socket permissions and unavailable-supervisor errors;
- operation serialization, idempotency, timeouts, rollback, and atomic state;
- Gateway API schemas, stable errors, localization, and log redaction;
- ASR/TTS UI confirmation, progress, retry, error, and ready states;
- persistent ASR selectors while workers are stopped;
- no automatic microphone permission, capture, synthesis, or playback.

Docker integration tests cover:

- Gateway continuity during worker reconciliation;
- exclusive ASR-to-TTS and TTS-to-ASR transitions;
- GPU memory release before starting the exclusive peer;
- ASR catalog restoration and TTS readiness;
- repeated reset idempotency and concurrent-operation rejection;
- recovery after a forced worker startup failure.

High-VRAM acceptance separately verifies `concurrent`: ASR and TTS remain
healthy together, page navigation causes no eviction, and a single workload
reset leaves the other ready. Multi-GPU placement is accepted only on a host
with explicit device assignments.

Real-device tests still require explicit user clicks for device checks,
recording, generation, and playback.

## Non-goals

- Exposing Docker controls to the browser or Gateway.
- Automatically selecting a high-memory policy from total VRAM alone without
  configured model budgets and usable-memory preflight.
- Implementing the Agent provider in this change.
- Starting microphone capture, TTS generation, or playback as part of reset.
- Persisting browser reference audio or generated speech.
