#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi
LOCAL_PORT=${AGENT_SPEAK_PORT:-8765}
HTTPS_PORT=${AGENT_SPEAK_TAILSCALE_HTTPS_PORT:-8765}
ACTION=${1:-start}
MODE=local
PYTHON_RUNNER=()

if ! command -v tailscale >/dev/null 2>&1; then
  echo "TAILSCALE_HTTPS_ERROR tailscale CLI is not installed" >&2
  exit 1
fi

configure_python_runner() {
  if command -v docker >/dev/null 2>&1; then
    local gateway_id
    if ! gateway_id=$(docker compose ps --status running -q gateway); then
      echo "TAILSCALE_HTTPS_ERROR Docker Gateway detection failed; check Docker daemon and Compose access." >&2
      exit 1
    fi
    if [[ -n "$gateway_id" ]]; then
      MODE=docker
      PYTHON_RUNNER=(docker compose exec -T gateway python)
      return
    fi
  fi

  MODE=local
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "TAILSCALE_HTTPS_ERROR Agent Speak is not running in Docker and the local .venv is unavailable. Run ./run.sh --build." >&2
    exit 1
  fi
  PYTHON_RUNNER=("$VENV_DIR/bin/python")
}

run_python() {
  "${PYTHON_RUNNER[@]}" "$@"
}

get_dns_name() {
  tailscale status --json | run_python -c '
import json
import sys

state = json.load(sys.stdin)
if state.get("BackendState") != "Running":
    raise SystemExit("Tailscale is not running or authenticated")
dns_name = state.get("Self", {}).get("DNSName", "").rstrip(".")
if not dns_name:
    raise SystemExit("Tailscale MagicDNS name is unavailable")
print(dns_name)
'
}

case "$ACTION" in
  start)
    configure_python_runner
    curl --silent --show-error --fail --max-time 4 \
      "http://127.0.0.1:$LOCAL_PORT/api/v1/health" >/dev/null || {
        echo "TAILSCALE_HTTPS_ERROR local service is unavailable; run ./run.sh --build" >&2
        exit 1
      }
    DNS_NAME=$(get_dns_name)
    tailscale serve --bg --yes --https="$HTTPS_PORT" "http://127.0.0.1:$LOCAL_PORT" >/dev/null
    echo "TAILSCALE_HTTPS_OK mode=$MODE url=https://$DNS_NAME:$HTTPS_PORT local=http://127.0.0.1:$LOCAL_PORT"
    ;;
  smoke)
    configure_python_runner
    DNS_NAME=$(get_dns_name)
    URL="https://$DNS_NAME:$HTTPS_PORT"
    curl --silent --show-error --fail --max-time 15 "$URL/api/v1/health" \
      | run_python -c 'import json, sys; data=json.load(sys.stdin); assert data["status"] == "ok" and data["storage_ready"]'
    curl --silent --show-error --fail --max-time 15 "$URL/" \
      | run_python -c 'import sys; assert "Agent Speak" in sys.stdin.read()'
    echo "TAILSCALE_HTTPS_SMOKE_OK mode=$MODE url=$URL health=ok root=ok"
    ;;
  status)
    tailscale serve status
    ;;
  stop)
    tailscale serve --yes --https="$HTTPS_PORT" off
    echo "TAILSCALE_HTTPS_STOPPED port=$HTTPS_PORT"
    ;;
  *)
    echo "Usage: $0 {start|smoke|status|stop}" >&2
    exit 2
    ;;
esac
