# NVIDIA GPU Auto-Detection Design

Date: 2026-07-20

## Goal

Agent Speak should use an NVIDIA GPU automatically when the host and Docker runtime can support it, while preserving a reliable CPU path on every other host. The selected accelerator must be visible to operators and to API clients. Existing `/api/v1` routes and provider boundaries remain unchanged.

## Scope

This iteration supports NVIDIA GPUs through CUDA. GPU model, VRAM size, and device count may vary. AMD and Intel GPU acceleration are out of scope; those hosts use the CPU path.

The default mode is `auto`. Operators may override it with `AGENT_SPEAK_ACCELERATOR=cpu` or `AGENT_SPEAK_ACCELERATOR=nvidia`.

## Approaches Considered

### Selected: CPU base plus GPU Compose override

The existing CPU-safe Compose definition remains the baseline. A separate GPU override requests NVIDIA devices and selects an image containing the CUDA libraries required by the ASR runtime. `run.sh` chooses the Compose file set after host preflight checks.

This keeps CPU-only downloads small, preserves startup on non-NVIDIA hosts, and makes the GPU-specific runtime explicit.

### Rejected: one universal CUDA image

A universal image simplifies selection but forces CPU-only users to download and store CUDA and cuDNN libraries they cannot use.

### Rejected: always request a GPU

An unconditional GPU reservation prevents the service from starting on CPU-only hosts or hosts without the NVIDIA Container Toolkit.

## Runtime Modes

`AGENT_SPEAK_ACCELERATOR` accepts exactly three values:

- `auto` (default): use the NVIDIA override only when every preflight check passes; otherwise print the failed check and continue on CPU.
- `cpu`: skip NVIDIA checks and use the base Compose definition.
- `nvidia`: require every NVIDIA preflight check to pass; fail before Compose startup when a check fails.

Invalid values fail immediately with an actionable error.

## NVIDIA Preflight

`run.sh` owns host-level accelerator selection. The preflight is side-effect free and checks, in order:

1. `nvidia-smi` exists and can enumerate at least one GPU.
2. Docker is reachable and Compose v2 is available.
3. Docker's reported runtimes include the configured NVIDIA runtime.

The preflight returns a structured shell result containing the selected mode and a short reason. All lifecycle commands that address the Gateway use one shared Compose-command builder so `--build`, `--up`, `--down`, `--status`, and smoke checks cannot accidentally select different file sets.

The selected commands are:

```text
CPU:    docker compose -f compose.yaml ...
NVIDIA: docker compose -f compose.yaml -f compose.gpu.yaml ...
```

In `auto` mode, a failed preflight selects CPU before containers start. It does not start a partially configured GPU service and retry after failure. In `nvidia` mode, the same failure is fatal.

## Container Design

`compose.yaml` remains CPU-safe and does not request a GPU. `compose.gpu.yaml` changes only the Gateway service:

- build or select the GPU runtime image;
- reserve all available NVIDIA GPU devices using the Compose GPU capability contract;
- pass through the original `AGENT_SPEAK_ACCELERATOR` value so the provider can distinguish `auto` from strict `nvidia` mode.

The GPU image contains CUDA 12 user-space libraries compatible with the pinned Faster-Whisper/CTranslate2 dependency, including the required cuBLAS and cuDNN runtime. The NVIDIA Container Toolkit supplies host driver access. Driver files are not copied from the host or baked into the image.

The CPU image and GPU image expose the same entrypoint, application files, volumes, health check, ports, and `/api/v1` contract.

References:

- [Docker Compose GPU support](https://docs.docker.com/compose/how-tos/gpu-support/)
- [Faster-Whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu)

## Provider Device Selection

Host selection and provider selection are separate checks:

1. `run.sh` decides whether Docker may receive the GPU.
2. The ASR provider verifies CUDA availability inside the running container before loading the model.

The configured ASR provider receives the external `auto`, `cpu`, or `nvidia` value unchanged. In `auto`, it selects CUDA only when CUDA is visible inside the container and otherwise selects CPU. `cpu` always selects CPU, while `nvidia` requires CUDA. The provider reports the device it actually initialized as `cpu` or `cuda`.

For Faster-Whisper:

- CUDA uses an explicitly supported GPU compute type, preferring `float16` on the selected NVIDIA path.
- CPU continues to use `int8` with the existing bounded thread configuration.
- In external `auto` mode, CUDA initialization failure is recorded and the provider falls back once to CPU before accepting ASR traffic.
- In external `nvidia` mode, CUDA initialization failure keeps the ASR capability unready and produces an actionable startup or stage error; it never silently uses CPU.

Fallback catches only accelerator initialization failures. Invalid models, corrupt files, and transcription errors are not mislabeled as GPU detection failures.

## Status and Capabilities

`./run.sh --status` reports three independent facts:

- host detection: NVIDIA GPU available or unavailable, with reason;
- Compose selection: CPU base or NVIDIA override;
- Gateway capability: ASR provider's actual device, obtained from `/api/v1/capabilities` when the Gateway is healthy.

The existing capability schema already contains `device`, so no response shape changes are needed. The provider value must reflect the initialized device rather than the requested device.

Status output must not include GPU UUIDs, credentials, environment secrets, or full driver diagnostics.

## Failure Handling

- CPU-only host in `auto`: start normally on CPU and print one concise fallback reason.
- NVIDIA driver present but Container Toolkit missing in `auto`: start on CPU and identify the missing Docker capability.
- Any failed NVIDIA preflight in `nvidia`: exit nonzero before starting the Gateway.
- CUDA libraries incompatible inside the container in `auto`: provider records the initialization failure, falls back to CPU once, and reports `device=cpu`.
- CUDA libraries incompatible inside the container in `nvidia`: fail readiness with an actionable error.
- GPU becomes unavailable after model initialization: return the existing stable stage error envelope; do not repeatedly reload or switch devices during an active request.

## Security and Data Handling

The GPU override grants only the GPU capability. It does not use privileged mode, broad host `/dev` mounts, or host CUDA directory mounts. Existing audio, model, data, and runtime volume boundaries remain unchanged.

No environment file, credentials, recordings, voice features, runtime data, model weights, logs, or private Agent state are committed.

## Test Strategy

New tests are written before implementation and cover:

1. `auto` selects the GPU override when all NVIDIA preflight probes succeed.
2. `auto` selects CPU and reports the reason for each failed probe.
3. `cpu` never invokes NVIDIA probes.
4. `nvidia` fails before Compose startup when any probe fails.
5. Invalid accelerator settings fail with a stable message.
6. Every lifecycle command uses the same selected Compose file set.
7. GPU Compose configuration requests the `gpu` capability without privileged mode or broad device mounts.
8. Provider CUDA initialization selects the GPU compute type and reports `device=cuda`.
9. Provider initialization falls back once in `auto`, remains strict in `nvidia`, and does not swallow unrelated failures.
10. Existing CPU tests and `/api/v1` contract tests continue to pass without GPU access.

Host integration verification runs separately from the hermetic test container:

- `./run.sh --status` on a CPU path;
- forced CPU startup on an NVIDIA host;
- automatic NVIDIA startup on a host with the Container Toolkit;
- `nvidia-smi` or an equivalent CUDA visibility probe inside the GPU Gateway;
- `/api/v1/capabilities` reports the initialized device.

## Acceptance Criteria

- A CPU-only or unsupported-GPU host starts Agent Speak without editing Compose files.
- A supported NVIDIA host with a working Container Toolkit automatically starts the GPU configuration.
- Operators can force CPU or require NVIDIA deterministically.
- Automatic fallback is explicit in status output and never changes public API shapes.
- The Gateway never claims CUDA unless the ASR provider initialized CUDA successfully.
- The existing test suite remains green in a no-GPU test environment.
