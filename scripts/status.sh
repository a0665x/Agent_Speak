#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
if [[ -f "$ROOT_DIR/.env" ]]; then set -a; source "$ROOT_DIR/.env"; set +a; fi
PORT=${AGENT_SPEAK_PORT:-8765}

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "STATUS_ERROR .venv missing; run ./scripts/setup.sh" >&2
  exit 1
fi

if curl --silent --fail --max-time 2 "http://127.0.0.1:$PORT/api/v1/health" >/dev/null; then
  echo "STATUS_OK service=running port=$PORT python=$($VENV_DIR/bin/python --version 2>&1)"
else
  echo "STATUS_STOPPED service=stopped port=$PORT python=$($VENV_DIR/bin/python --version 2>&1)"
  echo "Start it with ./scripts/run.sh"
  exit 3
fi
