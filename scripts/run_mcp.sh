#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Project .venv is missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi

# stdout is reserved exclusively for MCP JSON-RPC framing. The Python entry
# point loads .env with python-dotenv instead of executing it as shell code.
exec env PYTHONPATH="$ROOT_DIR/src" "$VENV_DIR/bin/python" -m agent_speak.mcp_server