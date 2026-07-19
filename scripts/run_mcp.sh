#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

# stdout is reserved exclusively for MCP JSON-RPC framing.
if [[ -f /.dockerenv && -d /app/src/agent_speak ]]; then
  exec env PYTHONPATH=/app/src python -m agent_speak.mcp_server
fi

if command -v docker >/dev/null 2>&1 && docker compose ps --status running -q gateway 2>/dev/null | grep -q .; then
  exec docker compose exec -T \
    -e AGENT_SPEAK_URL="${AGENT_SPEAK_URL:-http://127.0.0.1:8765}" \
    gateway env PYTHONPATH=/app/src python -m agent_speak.mcp_server
fi

# Developer fallback only; public operation is Docker-first.
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  exec env PYTHONPATH="$ROOT_DIR/src" "$ROOT_DIR/.venv/bin/python" -m agent_speak.mcp_server
fi

echo "Agent Speak is not running. Start it with ./run.sh --build." >&2
exit 1
