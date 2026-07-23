# Runtime

## Docker-first operation

Public operation uses one root entrypoint. Run `./run.sh --build` to build the multi-architecture Python image and start the Gateway. The same command owns normal lifecycle actions:

- `--up`, `--down`, `--down_up`, `--restart`
- `--rebuild` for a no-cache rebuild
- `--models` for explicit pinned model provisioning
- `--status`, `--logs`, `--test`, `--help`

`./run.sh --logs` tails Gateway, ASR worker, and correction worker output. Use `./run.sh --logs gateway`, `./run.sh --logs asr-worker`, or `./run.sh --logs correction-worker` to isolate one service. Invalid service names fail instead of being passed to Compose.

`compose.yaml` publishes the service to `127.0.0.1:${AGENT_SPEAK_PORT:-8765}`, maps host `/dev/snd` into the container by default, adds the host audio group, and uses a healthcheck plus `restart: unless-stopped`. Host `data/`, `runtime/`, and `models/` directories are bind-mounted to `/app` and survive container recreation. Their host paths can be overridden with `AGENT_SPEAK_DATA_PATH`, `AGENT_SPEAK_RUNTIME_PATH`, and `AGENT_SPEAK_MODELS_PATH`. They are ignored by Git and excluded from the Docker build context together with credentials and private Agent state.

The image supports Docker's native `linux/amd64` and `linux/arm64` platforms. Gateway, ASR runtime, test, and model-downloader are separate Docker targets so the public API does not carry every inference build dependency. `./run.sh --models` is the only production path that downloads weights: a pinned manifest provisions Faster Whisper Small, Breeze-ASR-25, Qwen3-ASR 1.7B, Qwen2.5 correction, and Piper `zh_CN-huayan-medium`. It preflights disk space, downloads into model-specific partial directories, validates exact revisions and required files, then atomically publishes each directory. Normal startup runs verify-only and fails with a bounded instruction when an artifact is absent; no entrypoint or first ASR call downloads weights lazily.

`AGENT_SPEAK_ACCELERATOR=auto` is the default. It selects the separate NVIDIA image only when `nvidia-smi` and Docker's NVIDIA runtime are both ready; otherwise it prints the reason and starts the CPU image. Use `cpu` to force the portable CPU/INT8 path or `nvidia` to require CUDA and fail instead of falling back. NVIDIA mode requires the NVIDIA Container Toolkit and builds `agent-speak:gpu-local` with CUDA 12 and cuDNN 9. The GPU override requests only the Compose `gpu` capability; it does not use privileged mode, broad `/dev` mounts, or host CUDA directory mounts.

Optional settings are read by Docker Compose from an untracked `.env`; `.env.example` is the public reference. `run.sh` imports only a strict operational whitelist from `docker compose config --environment` rather than executing `.env` as shell code, so custom bind paths, identity overrides, and the advertised host/port match Compose's effective configuration. Compose passes validated `AGENT_SPEAK_*` values to the application. The container listens on `0.0.0.0:8765` internally, while host publication remains loopback-only by default.

## MCP process

After `./run.sh --build`, an external MCP host executes `./scripts/run_mcp.sh`. On the host, the script attaches a stdio MCP process to the running Gateway container with `docker compose exec -T`. Inside a container it runs Python directly. A local `.venv` path remains only as a developer fallback and is not the public quick start.

stdout is reserved for MCP JSON-RPC. ALSA subprocess calls use argv without a shell, validate device names, enforce timeouts, limit capture to 1–30 seconds, and delete temporary WAV files. Playback is opt-in and reports `played=true` only after `aplay` succeeds.

## Private HTTPS phone access

Tailscale Serve remains a host concern because the application is published on loopback. `./scripts/tailscale_https.sh start` proxies the configured private HTTPS port to `127.0.0.1:${AGENT_SPEAK_PORT:-8765}`. Run `./scripts/tailscale_https.sh smoke` before sharing a phone URL. Do not expose this unauthenticated MVP directly to an untrusted LAN or public internet.

## Limits and state

Pydantic validates all runtime settings. Browser MediaRecorder output is converted client-side to 16-bit PCM WAV. Audio bytes/duration, sessions, retained events, subscriber queues, and generated artifacts are bounded through `.env.example` settings.

The Docker healthcheck calls `/api/v1/health`. `./run.sh --status` exits successfully only when the Gateway container is healthy and reports capture/playback availability from real `arecord -l` and `aplay -l` probes, selected Compose accelerator, resolved resource policy/profile, ASR/TTS lifecycle states, and actual provider devices. `./run.sh --test` launches the dedicated CPU `gateway-test` one-shot service with no production bind mounts, no `/dev/snd`, no GPU reservation, and no network; it skips model bootstrap, runs pytest and JavaScript syntax checking, and removes the test container afterward.

Legacy scripts under `scripts/` remain focused smoke and developer utilities rather than the main lifecycle interface. `./scripts/health_smoke.sh`, `./scripts/smoke_api.sh`, and `./scripts/tailscale_https.sh` are Docker-aware: from any working directory they first detect this repository's running Compose `gateway` and execute Python validation inside it, so a Release install does not need a host `.venv`. Tailscale CLI and Serve configuration remain host operations; only status JSON, health JSON, and WebUI content validation use the selected Python runtime. When Compose detection succeeds but no Gateway is running, all three scripts retain the local `.venv` fallback. For `tailscale_https.sh`, a Docker daemon or Compose access error is reported rather than hidden as a local fallback. Success is reported with `mode=docker|local`, including `TAILSCALE_HTTPS_SMOKE_OK mode=docker|local` for the HTTPS smoke.

## Diagnostic logs

Gateway and ASR worker diagnostics are JSON Lines written both to container output and bounded rotating files. Gateway files live at `runtime/logs/gateway.jsonl`; the independently owned ASR mount writes `runtime/asr-worker/logs/asr-worker.jsonl`. The separate mount prevents the root ASR image and non-root Gateway from competing for one private directory. Defaults are `INFO`, 5 MiB per file, and five backups; configure `AGENT_SPEAK_LOG_LEVEL`, `AGENT_SPEAK_LOG_MAX_BYTES`, and `AGENT_SPEAK_LOG_BACKUP_COUNT` in the untracked `.env`.

Levels are operational contracts: `ERROR` is failed activation or an unexpected unrecoverable service error; `WARNING` is retryable provider failure, empty result, or bounded queue pressure; `INFO` is request/model/session lifecycle; `DEBUG` adds inference timing, mode, device, and queue state. Allowed context includes correlation ID, anonymized session reference, stage, model, device, mode, duration, status/error code, exception class, and retry count.

Audio bytes, encodings, transcript/correction text, browser device labels, credentials, authorization/cookie headers, request bodies, exception messages, raw session IDs, and private paths are forbidden. Public API errors remain bounded. Logs and backups are private runtime data and must never be committed.

Troubleshooting order is:

1. `./run.sh --status`
2. `./run.sh --logs asr-worker` for recognition/model failures, or `./run.sh --logs gateway` for API/WebSocket failures
3. `curl -fsS http://127.0.0.1:8765/api/v1/models` to compare requested, active, and ready state
4. `./run.sh --test` before changing behavior

## Resource Orchestrator and inference profiles

`./run.sh --up` is an alias for `./run.sh --asr-up`. Both `--asr-up` and NVIDIA-only `--tts-up` keep the Gateway running, start the host Resource Orchestrator if needed, and reconcile `asr_only` or `tts_only`. The supervisor owns only fixed Compose worker actions, serializes transitions through `runtime/resource-control/control.sock`, and writes atomic bounded state beside the socket. `--down`, `--down_up`, and `--restart` ask the supervisor to shut down before Compose teardown. No transition deletes `data/`, `runtime/`, or `models/`.

`AGENT_SPEAK_RESOURCE_POLICY=auto` is the safe default. It resolves to `exclusive` unless detected VRAM exceeds the configured reserve plus all workload budgets. Set `exclusive` for low-VRAM hosts, `concurrent` when ASR/correction and TTS fit one GPU, or `multi_gpu` when Compose device visibility is explicitly mapped per service. Budget and timeout settings are documented in `.env.example`. Reconciliation phases are bounded and observable at `/api/v1/resources`; a failed reset exposes a stable error code and operator hint rather than a raw subprocess error.

`./run.sh --models` prepares every pinned artifact, including roughly 9.6 GB for VoxCPM2, only after the shared preflight preserves an 8 GiB safety reserve. The 40 GB free-space observation made during design was a point-in-time preflight, not a promise of future capacity. Use `./run.sh --status` to see `resource_policy`, `profile`, `asr_state`, and `tts_state`, and `./run.sh --logs tts-worker` for private worker startup/model failures. CPU-only systems report TTS unavailable rather than silently attempting a slow fallback.

The pinned TTS image installs `voxcpm==2.0.3` in addition to vLLM-Omni. On
Turing-class NVIDIA GPUs such as SM 7.5, the worker uses FP16, a bounded 256 MiB
KV cache, eager execution, and a writable executable Triton cache outside the
`noexec` `/tmp` mount. A build-time, exact-source guarded adapter patch aligns
the native VoxCPM2 and AudioVAE dtype boundaries with FP16; the image build
fails closed if the pinned upstream source changes. Native vLLM INFO/access
logging is disabled because it includes synthesis text. Warning and error
records remain available through `./run.sh --logs tts-worker`.
