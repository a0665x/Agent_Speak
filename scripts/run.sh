#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Project .venv is missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi
HOST=${AGENT_SPEAK_HOST:-127.0.0.1}
PORT=${AGENT_SPEAK_PORT:-8765}
echo "RUN_STARTING url=http://127.0.0.1:$PORT docs=http://127.0.0.1:$PORT/docs"
cd "$ROOT_DIR"
exec env PYTHONPATH="$ROOT_DIR/src" "$VENV_DIR/bin/python" -m uvicorn agent_speak.app:app --host "$HOST" --port "$PORT"
