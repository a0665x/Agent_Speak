#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT_DIR"

COMPOSE=(docker compose -f compose.yaml)
ACCELERATOR_SELECTED=cpu
ACCELERATOR_REASON="forced CPU"

usage() {
  cat <<'EOF'
Agent Speak — Docker-first operator

Usage: ./run.sh OPTION

  --build       Build the image, then start the gateway
  --up          Start the gateway in the background
  --down        Stop and remove containers; preserve data, runtime, and models
  --down_up     Recreate the running stack (same behavior as --restart)
  --restart     Recreate the running stack (same behavior as --down_up)
  --rebuild     Stop, rebuild without cache, and start
  --status      Show container and gateway health
  --logs        Show the latest 100 gateway log lines
  --test        Run the complete test suite in an isolated container
  --help        Show this help

The gateway publishes only to 127.0.0.1 by default. Docker Compose maps
/dev/snd into the container for ALSA microphone and speaker access.
EOF
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker is required. Install Docker Engine with Compose v2." >&2
    exit 127
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: Docker Compose v2 is required (docker compose)." >&2
    exit 127
  fi
}

load_compose_environment() {
  local key value
  while IFS='=' read -r key value; do
    case "$key" in
      AGENT_SPEAK_DATA_PATH|AGENT_SPEAK_RUNTIME_PATH|AGENT_SPEAK_MODELS_PATH|\
      AGENT_SPEAK_PUBLISH_HOST|AGENT_SPEAK_PORT|AGENT_SPEAK_UID|AGENT_SPEAK_GID|\
      AGENT_SPEAK_AUDIO_GID|AGENT_SPEAK_ACCELERATOR|AGENT_SPEAK_ASR_CUDA_COMPUTE_TYPE)
        # Explicit process environment wins. Otherwise import only this strict
        # operational whitelist from Compose's safely parsed .env output.
        if [[ ! -v "$key" ]]; then
          printf -v "$key" '%s' "$value"
          export "$key"
        fi
        ;;
    esac
  done < <(compose config --environment 2>/dev/null)
}

compose() {
  "${COMPOSE[@]}" "$@"
}

configure_accelerator() {
  local requested=${AGENT_SPEAK_ACCELERATOR:-auto}
  local failure=""
  case "$requested" in
    cpu)
      ACCELERATOR_SELECTED=cpu
      ACCELERATOR_REASON="forced CPU"
      ;;
    auto|nvidia)
      if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi -L >/dev/null 2>&1; then
        failure="NVIDIA GPU or driver is unavailable"
      elif ! docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'; then
        failure="NVIDIA Docker runtime is unavailable"
      fi
      if [[ -z "$failure" ]]; then
        COMPOSE+=( -f compose.gpu.yaml )
        ACCELERATOR_SELECTED=nvidia
        ACCELERATOR_REASON="NVIDIA preflight passed"
      elif [[ "$requested" == nvidia ]]; then
        echo "ERROR: NVIDIA acceleration is required: $failure" >&2
        return 1
      else
        ACCELERATOR_SELECTED=cpu
        ACCELERATOR_REASON="$failure"
        echo "WARNING: $failure; falling back to CPU." >&2
      fi
      ;;
    *)
      echo "ERROR: AGENT_SPEAK_ACCELERATOR must be auto, cpu, or nvidia (got: $requested)" >&2
      return 2
      ;;
  esac
  export AGENT_SPEAK_ACCELERATOR=$requested
  export AGENT_SPEAK_EFFECTIVE_ACCELERATOR=$ACCELERATOR_SELECTED
  echo "ACCELERATOR_SELECTED mode=$ACCELERATOR_SELECTED reason=$ACCELERATOR_REASON"
}

prepare_runtime() {
  mkdir -p -- \
    "${AGENT_SPEAK_DATA_PATH:-./data}" \
    "${AGENT_SPEAK_RUNTIME_PATH:-./runtime}" \
    "${AGENT_SPEAK_MODELS_PATH:-./models}"
  export AGENT_SPEAK_UID=${AGENT_SPEAK_UID:-$(id -u)}
  export AGENT_SPEAK_GID=${AGENT_SPEAK_GID:-$(id -g)}
  if compgen -G '/dev/snd/controlC*' >/dev/null; then
    local controls=(/dev/snd/controlC*)
    export AGENT_SPEAK_AUDIO_GID=${AGENT_SPEAK_AUDIO_GID:-$(stat -c '%g' "${controls[0]}")}
  elif [[ -e /dev/snd ]]; then
    echo "WARNING: /dev/snd has no ALSA control device; using fallback audio GID." >&2
    export AGENT_SPEAK_AUDIO_GID=${AGENT_SPEAK_AUDIO_GID:-29}
  else
    echo "WARNING: /dev/snd is unavailable; Compose startup will fail until an audio device is present." >&2
    export AGENT_SPEAK_AUDIO_GID=${AGENT_SPEAK_AUDIO_GID:-29}
  fi
}

wait_for_health() {
  local attempts=${AGENT_SPEAK_HEALTH_ATTEMPTS:-90}
  local container_id health
  for ((i=1; i<=attempts; i++)); do
    container_id=$(compose ps --all -q gateway 2>/dev/null || true)
    if [[ -n "$container_id" ]]; then
      health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)
      if [[ "$health" == "healthy" ]]; then
        echo "GATEWAY_READY web=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765} realtime=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/asr_realtime docs=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/docs"
        return 0
      fi
      if [[ "$health" == "unhealthy" || "$health" == "exited" ]]; then
        compose logs --tail 80 gateway >&2 || true
        echo "ERROR: gateway became $health" >&2
        return 1
      fi
    fi
    sleep 1
  done
  compose logs --tail 80 gateway >&2 || true
  echo "ERROR: gateway health timeout" >&2
  return 1
}

if [[ "${1:---help}" == "--help" || "${1:---help}" == "-h" || "${1:---help}" == "help" ]]; then
  usage
  exit 0
fi

require_docker
load_compose_environment
set +e
configure_accelerator
accelerator_status=$?
set -e
if (( accelerator_status != 0 )); then
  exit "$accelerator_status"
fi
prepare_runtime

case "$1" in
  --build)
    compose build
    compose up -d
    wait_for_health
    ;;
  --up)
    compose up -d
    wait_for_health
    ;;
  --down)
    compose down
    echo "GATEWAY_DOWN persistent_data_preserved=true"
    ;;
  --down_up|--restart)
    compose down
    compose up -d
    wait_for_health
    ;;
  --rebuild)
    compose down
    compose build --no-cache
    compose up -d
    wait_for_health
    ;;
  --status)
    compose ps
    container_id=$(compose ps --all -q gateway)
    if [[ -z "$container_id" ]]; then
      echo "STATUS_STOPPED"
      exit 1
    fi
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")
    capture=unavailable
    playback=unavailable
    capture_listing=$(compose exec -T gateway arecord -l 2>&1 || true)
    playback_listing=$(compose exec -T gateway aplay -l 2>&1 || true)
    if grep -Eq '^card [0-9]+:' <<<"$capture_listing"; then
      capture=available
    fi
    if grep -Eq '^card [0-9]+:' <<<"$playback_listing"; then
      playback=available
    fi
    asr_device=$(compose exec -T gateway python -c '
import json
import urllib.request
payload = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/v1/capabilities", timeout=3))
print(next(item["device"] for item in payload["providers"] if item["stage"] == "asr"))
' 2>/dev/null || printf 'unknown')
    if [[ -z "$asr_device" ]]; then
      asr_device=unknown
    fi
    correction_device=$(compose exec -T gateway python -c '
import json
import urllib.request
payload = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/v1/capabilities", timeout=3))
print(next(item["device"] for item in payload["providers"] if item["stage"] == "correction"))
' 2>/dev/null || printf 'unknown')
    if [[ -z "$correction_device" ]]; then
      correction_device=unknown
    fi
    echo "STATUS_${health^^} web=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765} realtime=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/asr_realtime docs=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/docs capture=$capture playback=$playback accelerator=$ACCELERATOR_SELECTED asr_device=$asr_device correction_device=$correction_device"
    [[ "$health" == "healthy" ]]
    ;;
  --logs)
    compose logs --tail 100 gateway asr-worker correction-worker
    ;;
  --test)
    compose run --rm --no-deps gateway-test bash -lc '
      python -m pytest -q -p no:cacheprovider &&
      node --check web/app.js &&
      node --check web/codex-recorder-core.js &&
      node --check web/codex.js &&
      node tests/codex_recorder_core.test.js
    '
    compose run --rm --no-deps frontend-test
    echo TESTS_OK
    ;;
  --help|-h|help)
    usage
    ;;
  *)
    echo "ERROR: unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
esac
