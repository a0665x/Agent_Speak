#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
if [[ -f "$ROOT_DIR/.env" ]]; then set -a; source "$ROOT_DIR/.env"; set +a; fi
PORT=${AGENT_SPEAK_PORT:-8765}

if [[ -x "$VENV_DIR/bin/python" ]]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
elif [[ -f /.dockerenv ]]; then
  PYTHON_BIN=python
else
  echo "STATUS_ERROR .venv missing; use Docker-first ./run.sh --status or run ./scripts/setup.sh" >&2
  exit 1
fi

if "$PYTHON_BIN" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$PORT/api/v1/health', timeout=2).read()" >/dev/null 2>&1; then
  echo "STATUS_OK service=running port=$PORT python=$($PYTHON_BIN --version 2>&1)"
else
  echo "STATUS_STOPPED service=stopped port=$PORT python=$($PYTHON_BIN --version 2>&1)"
  echo "Start the public stack with ./run.sh --up"
  exit 3
fi
