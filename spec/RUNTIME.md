# Runtime and Operations

Use `./scripts/setup.sh` once, `./scripts/run.sh` to start, `./scripts/status.sh` for state, and `./scripts/test.sh` for tests. `./scripts/smoke_api.sh` validates a running service. `./scripts/mic_smoke.sh` records a bounded sample and reports signal stats.

Private phone access uses Tailscale Serve while the application remains bound to localhost. Run `./scripts/tailscale_https.sh start` to create a persistent tailnet-only HTTPS proxy from `AGENT_SPEAK_TAILSCALE_HTTPS_PORT` (default `8765`) to the local application port, then run `./scripts/tailscale_https.sh smoke`. Success prints `TAILSCALE_HTTPS_OK url=...` followed by `TAILSCALE_HTTPS_SMOKE_OK ... health=ok root=ok`. Use `status` to inspect all Serve routes and `stop` to remove only this project's HTTPS port. The phone must be signed into the same tailnet; this is Tailscale Serve, not public Funnel exposure.

Configuration comes from `.env` copied from `.env.example`. Default bind is `127.0.0.1:8765`. External agent calls are opt-in. Runtime state and logs stay under ignored `runtime/` and `data/`. Binding `AGENT_SPEAK_HOST=0.0.0.0` exposes the unauthenticated, unencrypted MVP to the LAN and is appropriate only on a trusted network with host firewall controls; never expose it directly to an untrusted network or the public internet.

Settings are validated with Pydantic and loaded from `AGENT_SPEAK_*` variables using the standard library; `pydantic-settings` is intentionally not required. Browser MediaRecorder output is decoded and converted client-side to 16-bit PCM WAV because the server intentionally accepts a single bounded audio format.

Each operator script prints success signals and repair guidance.

`status.sh` exits 0 only for a running service. It prints `STATUS_STOPPED` and exits 3 when the virtual environment exists but the health endpoint is not running, while setup/configuration errors use other nonzero exits.

For MVP resource control, `AGENT_SPEAK_MAX_SESSIONS`, `AGENT_SPEAK_MAX_SESSION_EVENTS`, `AGENT_SPEAK_MAX_EVENT_QUEUE`, and `AGENT_SPEAK_MAX_ARTIFACTS` bound in-memory sessions, retained event history, each subscriber queue, and generated TTS artifacts. Old inactive sessions, old retained events, and old artifacts are removed first; a slow event subscriber retains the latest queued events.

`setup.sh` creates/uses only the project `.venv`. `health_smoke.sh` checks one endpoint; `smoke_api.sh` covers health, a live WebSocket turn, artifact creation, and speaker lifecycle against a running service. `mic_smoke.sh` writes its bounded capture to a temporary file and deletes it on exit.
