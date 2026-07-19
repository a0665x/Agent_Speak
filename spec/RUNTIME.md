# Runtime

## Docker-first operation

Public operation uses one root entrypoint. Run `./run.sh --build` to build the multi-architecture Python image and start the Gateway. The same command owns normal lifecycle actions:

- `--up`, `--down`, `--down_up`, `--restart`
- `--rebuild` for a no-cache rebuild
- `--status`, `--logs`, `--test`, `--help`

`compose.yaml` publishes the service to `127.0.0.1:${AGENT_SPEAK_PORT:-8765}`, maps host `/dev/snd` into the container by default, adds the host audio group, and uses a healthcheck plus `restart: unless-stopped`. Host `data/`, `runtime/`, and `models/` directories are bind-mounted to `/app` and survive container recreation. Their host paths can be overridden with `AGENT_SPEAK_DATA_PATH`, `AGENT_SPEAK_RUNTIME_PATH`, and `AGENT_SPEAK_MODELS_PATH`. They are ignored by Git and excluded from the Docker build context together with credentials and private Agent state.

The image supports Docker's native `linux/amd64` and `linux/arm64` platforms through `python:3.11-slim-bookworm`. It installs ALSA utilities and local inference dependencies. The entrypoint downloads Piper `zh_CN-huayan-medium` into persistent model storage only when missing. Faster-Whisper downloads lazily into `models/` on the first ASR request.

Optional settings are read by Docker Compose from an untracked `.env`; `.env.example` is the public reference. `run.sh` imports only a strict operational whitelist from `docker compose config --environment` rather than executing `.env` as shell code, so custom bind paths, identity overrides, and the advertised host/port match Compose's effective configuration. Compose passes validated `AGENT_SPEAK_*` values to the application. The container listens on `0.0.0.0:8765` internally, while host publication remains loopback-only by default.

## MCP process

After `./run.sh --build`, an external MCP host executes `./scripts/run_mcp.sh`. On the host, the script attaches a stdio MCP process to the running Gateway container with `docker compose exec -T`. Inside a container it runs Python directly. A local `.venv` path remains only as a developer fallback and is not the public quick start.

stdout is reserved for MCP JSON-RPC. ALSA subprocess calls use argv without a shell, validate device names, enforce timeouts, limit capture to 1–30 seconds, and delete temporary WAV files. Playback is opt-in and reports `played=true` only after `aplay` succeeds.

## Private HTTPS phone access

Tailscale Serve remains a host concern because the application is published on loopback. `./scripts/tailscale_https.sh start` proxies the configured private HTTPS port to `127.0.0.1:${AGENT_SPEAK_PORT:-8765}`. Run `./scripts/tailscale_https.sh smoke` before sharing a phone URL. Do not expose this unauthenticated MVP directly to an untrusted LAN or public internet.

## Limits and state

Pydantic validates all runtime settings. Browser MediaRecorder output is converted client-side to 16-bit PCM WAV. Audio bytes/duration, sessions, retained events, subscriber queues, and generated artifacts are bounded through `.env.example` settings.

The Docker healthcheck calls `/api/v1/health`. `./run.sh --status` exits successfully only when the Gateway container is healthy and reports capture/playback availability from real `arecord -l` and `aplay -l` probes. `./run.sh --test` launches the dedicated `gateway-test` one-shot service with no production bind mounts, no `/dev/snd`, and no network; it skips model bootstrap, runs pytest and JavaScript syntax checking, and removes the test container afterward.

Legacy scripts under `scripts/` remain focused smoke and developer utilities rather than the main lifecycle interface. `./scripts/health_smoke.sh`, `./scripts/smoke_api.sh`, and `./scripts/tailscale_https.sh` are Docker-aware: from any working directory they first detect this repository's running Compose `gateway` and execute Python validation inside it, so a Release install does not need a host `.venv`. Tailscale CLI and Serve configuration remain host operations; only status JSON, health JSON, and WebUI content validation use the selected Python runtime. When Compose detection succeeds but no Gateway is running, all three scripts retain the local `.venv` fallback. For `tailscale_https.sh`, a Docker daemon or Compose access error is reported rather than hidden as a local fallback. Success is reported with `mode=docker|local`, including `TAILSCALE_HTTPS_SMOKE_OK mode=docker|local` for the HTTPS smoke.
