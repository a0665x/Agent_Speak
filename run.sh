#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT_DIR"

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
      AGENT_SPEAK_AUDIO_GID)
        # Explicit process environment wins. Otherwise import only this strict
        # operational whitelist from Compose's safely parsed .env output.
        if [[ ! -v "$key" ]]; then
          printf -v "$key" '%s' "$value"
          export "$key"
        fi
        ;;
    esac
  done < <(docker compose config --environment 2>/dev/null)
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
    container_id=$(docker compose ps --all -q gateway 2>/dev/null || true)
    if [[ -n "$container_id" ]]; then
      health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)
      if [[ "$health" == "healthy" ]]; then
        echo "GATEWAY_READY web=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765} docs=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/docs"
        return 0
      fi
      if [[ "$health" == "unhealthy" || "$health" == "exited" ]]; then
        docker compose logs --tail 80 gateway >&2 || true
        echo "ERROR: gateway became $health" >&2
        return 1
      fi
    fi
    sleep 1
  done
  docker compose logs --tail 80 gateway >&2 || true
  echo "ERROR: gateway health timeout" >&2
  return 1
}

if [[ "${1:---help}" == "--help" || "${1:---help}" == "-h" || "${1:---help}" == "help" ]]; then
  usage
  exit 0
fi

require_docker
load_compose_environment
prepare_runtime

case "$1" in
  --build)
    docker compose build
    docker compose up -d
    wait_for_health
    ;;
  --up)
    docker compose up -d
    wait_for_health
    ;;
  --down)
    docker compose down
    echo "GATEWAY_DOWN persistent_data_preserved=true"
    ;;
  --down_up|--restart)
    docker compose down
    docker compose up -d
    wait_for_health
    ;;
  --rebuild)
    docker compose down
    docker compose build --no-cache
    docker compose up -d
    wait_for_health
    ;;
  --status)
    docker compose ps
    container_id=$(docker compose ps --all -q gateway)
    if [[ -z "$container_id" ]]; then
      echo "STATUS_STOPPED"
      exit 1
    fi
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")
    capture=unavailable
    playback=unavailable
    capture_listing=$(docker compose exec -T gateway arecord -l 2>&1 || true)
    playback_listing=$(docker compose exec -T gateway aplay -l 2>&1 || true)
    if grep -Eq '^card [0-9]+:' <<<"$capture_listing"; then
      capture=available
    fi
    if grep -Eq '^card [0-9]+:' <<<"$playback_listing"; then
      playback=available
    fi
    echo "STATUS_${health^^} web=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765} docs=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/docs capture=$capture playback=$playback"
    [[ "$health" == "healthy" ]]
    ;;
  --logs)
    docker compose logs --tail 100 gateway
    ;;
  --test)
    docker compose run --rm --no-deps gateway-test bash -lc '
      python -m pytest -q -p no:cacheprovider &&
      node --check web/app.js &&
      node --check web/codex-recorder-core.js &&
      node --check web/codex.js &&
      node tests/codex_recorder_core.test.js &&
      echo TESTS_OK
    '
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
