#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
cd "$ROOT_DIR"

MODE=local
if command -v docker >/dev/null 2>&1 \
  && docker compose ps --status running -q gateway 2>/dev/null | grep -q .; then
  MODE=docker
  # The Python process runs inside the Gateway network namespace, where the
  # service always listens on its internal port regardless of host publishing.
  API_BASE=http://127.0.0.1:8765
  docker compose exec -T \
    -e API_BASE="$API_BASE" \
    gateway python - <<'PY'
import json
import os
import urllib.request

with urllib.request.urlopen(os.environ["API_BASE"] + "/api/v1/health", timeout=4) as response:
    data = json.load(response)
assert data["status"] == "ok" and data["storage_ready"]
PY
else
  if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    source "$ROOT_DIR/.env"
    set +a
  fi
  PORT=${AGENT_SPEAK_PORT:-8765}
  API_BASE=${API_BASE:-http://127.0.0.1:$PORT}
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "Agent Speak is not running in Docker and the local .venv is unavailable. Run ./run.sh --build." >&2
    exit 1
  fi
  API_BASE="$API_BASE" "$VENV_DIR/bin/python" - <<'PY'
import json
import os
import urllib.request

with urllib.request.urlopen(os.environ["API_BASE"] + "/api/v1/health", timeout=4) as response:
    data = json.load(response)
assert data["status"] == "ok" and data["storage_ready"]
PY
fi

echo "HEALTH_SMOKE_OK mode=$MODE api=$API_BASE"
