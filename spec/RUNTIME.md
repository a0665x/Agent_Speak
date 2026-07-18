# Runtime and Operations

Use `./scripts/setup.sh` once, `./scripts/run.sh` to start, `./scripts/status.sh` for state, and `./scripts/test.sh` for tests. `./scripts/smoke_api.sh` validates a running service. `./scripts/mic_smoke.sh` records a bounded sample and reports signal stats.

Configuration comes from `.env` copied from `.env.example`. Default bind is `0.0.0.0:8765`. External agent calls are opt-in. Runtime state and logs stay under ignored `runtime/` and `data/`.

Each operator script prints success signals and repair guidance.
