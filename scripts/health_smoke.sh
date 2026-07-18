#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
if [[ -f "$ROOT_DIR/.env" ]]; then set -a; source "$ROOT_DIR/.env"; set +a; fi
PORT=${AGENT_SPEAK_PORT:-8765}
if [[ ! -x "$VENV_DIR/bin/python" ]]; then echo "Run ./scripts/setup.sh first." >&2; exit 1; fi
payload=$(curl --silent --show-error --fail --max-time 4 "http://127.0.0.1:$PORT/api/v1/health")
PAYLOAD="$payload" "$VENV_DIR/bin/python" -c 'import json, os; data=json.loads(os.environ["PAYLOAD"]); assert data["status"] == "ok" and data["storage_ready"]'
echo "HEALTH_SMOKE_OK port=$PORT"
