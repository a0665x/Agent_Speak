#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
if [[ -f "$ROOT_DIR/.env" ]]; then set -a; source "$ROOT_DIR/.env"; set +a; fi
LOCAL_PORT=${AGENT_SPEAK_PORT:-8765}
HTTPS_PORT=${AGENT_SPEAK_TAILSCALE_HTTPS_PORT:-8765}
ACTION=${1:-start}

if ! command -v tailscale >/dev/null 2>&1; then
  echo "TAILSCALE_HTTPS_ERROR tailscale CLI is not installed" >&2
  exit 1
fi
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "TAILSCALE_HTTPS_ERROR .venv missing; run ./scripts/setup.sh" >&2
  exit 1
fi

get_dns_name() {
  local state_file
  state_file=$(mktemp)
  trap 'rm -f "$state_file"' RETURN
  tailscale status --json >"$state_file"
  "$VENV_DIR/bin/python" - "$state_file" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text())
if state.get("BackendState") != "Running":
    raise SystemExit("Tailscale is not running or authenticated")
dns_name = state.get("Self", {}).get("DNSName", "").rstrip(".")
if not dns_name:
    raise SystemExit("Tailscale MagicDNS name is unavailable")
print(dns_name)
PY
}

case "$ACTION" in
  start)
    curl --silent --show-error --fail --max-time 4 \
      "http://127.0.0.1:$LOCAL_PORT/api/v1/health" >/dev/null || {
        echo "TAILSCALE_HTTPS_ERROR local service is unavailable; run ./scripts/run.sh" >&2
        exit 1
      }
    DNS_NAME=$(get_dns_name)
    tailscale serve --bg --yes --https="$HTTPS_PORT" "http://127.0.0.1:$LOCAL_PORT" >/dev/null
    echo "TAILSCALE_HTTPS_OK url=https://$DNS_NAME:$HTTPS_PORT local=http://127.0.0.1:$LOCAL_PORT"
    ;;
  smoke)
    DNS_NAME=$(get_dns_name)
    URL="https://$DNS_NAME:$HTTPS_PORT"
    health=$(curl --silent --show-error --fail --max-time 15 "$URL/api/v1/health")
    HEALTH="$health" "$VENV_DIR/bin/python" -c 'import json, os; data=json.loads(os.environ["HEALTH"]); assert data["status"] == "ok" and data["storage_ready"]'
    page_file=$(mktemp)
    trap 'rm -f "$page_file"' EXIT
    curl --silent --show-error --fail --max-time 15 --output "$page_file" "$URL/"
    "$VENV_DIR/bin/python" - "$page_file" <<'PY'
import sys
from pathlib import Path

page = Path(sys.argv[1]).read_text()
assert "Agent Speak" in page
PY
    echo "TAILSCALE_HTTPS_SMOKE_OK url=$URL health=ok root=ok"
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
