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
  --models      Explicitly download and verify all pinned speech models
  --up          Start the ASR stack (alias for --asr-up)
  --asr-up      Keep the gateway running and reconcile the ASR-only profile
  --tts-up      Keep the gateway running and reconcile the TTS-only profile (NVIDIA only)
  --down        Stop and remove containers; preserve data, runtime, and models
  --down_up     Recreate the running stack (same behavior as --restart)
  --restart     Recreate the running stack (same behavior as --down_up)
  --rebuild     Stop, rebuild without cache, and start
  --status      Show container and gateway health
  --logs [SERVICE]
                Show the latest 100 log lines for all, gateway, asr-worker,
                correction-worker, or tts-worker (default: all)
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
      AGENT_SPEAK_AUDIO_GID|AGENT_SPEAK_ACCELERATOR|AGENT_SPEAK_ASR_CUDA_COMPUTE_TYPE|\
      AGENT_SPEAK_LOG_LEVEL|AGENT_SPEAK_LOG_MAX_BYTES|AGENT_SPEAK_LOG_BACKUP_COUNT|\
      AGENT_SPEAK_RESOURCE_POLICY|AGENT_SPEAK_RESOURCE_RESERVE_MB|\
      AGENT_SPEAK_RESOURCE_ASR_BUDGET_MB|AGENT_SPEAK_RESOURCE_CORRECTION_BUDGET_MB|\
      AGENT_SPEAK_RESOURCE_TTS_BUDGET_MB|AGENT_SPEAK_RESOURCE_DRAIN_TIMEOUT_SECONDS|\
      AGENT_SPEAK_RESOURCE_START_TIMEOUT_SECONDS|AGENT_SPEAK_RESOURCE_OPERATION_TIMEOUT_SECONDS|\
      AGENT_SPEAK_ASR_GPU_DEVICES|AGENT_SPEAK_CORRECTION_GPU_DEVICES|\
      AGENT_SPEAK_TTS_GPU_DEVICES)
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
    "${AGENT_SPEAK_RUNTIME_PATH:-./runtime}/asr-worker" \
    "${AGENT_SPEAK_RUNTIME_PATH:-./runtime}/resource-control" \
    "${AGENT_SPEAK_MODELS_PATH:-./models}"
  chmod 0700 "${AGENT_SPEAK_RUNTIME_PATH:-./runtime}/resource-control"
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
        echo "GATEWAY_READY web=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765} realtime=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/asr_realtime tts_clone=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/tts_clone_test docs=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/docs"
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

resource_runtime_dir() {
  printf '%s/resource-control' "${AGENT_SPEAK_RUNTIME_PATH:-./runtime}"
}

resource_cli() {
  PYTHONPATH="$ROOT_DIR/src" python3 -m agent_speak.resource_supervisor \
    --socket "$(resource_runtime_dir)/control.sock" client "$@"
}

start_resource_supervisor() {
  local control_dir pid_file log_file
  local -a command
  control_dir=$(resource_runtime_dir)
  pid_file="$control_dir/supervisor.pid"
  log_file="$control_dir/supervisor.log"
  mkdir -p -- "$control_dir"
  chmod 0700 "$control_dir"
  if resource_cli ping >/dev/null 2>&1; then
    return 0
  fi

  command=(
    python3 -m agent_speak.resource_supervisor
    --root "$ROOT_DIR"
    --socket "$control_dir/control.sock"
    --state "$control_dir/state.json"
    --policy "${AGENT_SPEAK_RESOURCE_POLICY:-auto}"
    --effective-accelerator "$ACCELERATOR_SELECTED"
    --compose-file "$ROOT_DIR/compose.yaml"
  )
  if [[ "$ACCELERATOR_SELECTED" == nvidia ]]; then
    command+=(--compose-file "$ROOT_DIR/compose.gpu.yaml")
  fi
  command+=(server)
  PYTHONPATH="$ROOT_DIR/src" nohup "${command[@]}" \
    >>"$log_file" 2>&1 &
  printf '%s\n' "$!" >"$pid_file"
  chmod 0600 "$pid_file"

  for ((attempt=1; attempt<=50; attempt++)); do
    if resource_cli ping >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.1
  done
  echo "ERROR: resource supervisor failed to start; inspect $log_file" >&2
  return 1
}

stop_resource_supervisor() {
  resource_cli shutdown >/dev/null 2>&1 || true
}

start_control_plane() {
  start_resource_supervisor
  compose up -d gateway
  wait_for_health
}

start_asr_mode() {
  start_control_plane
  resource_cli reconcile asr_only --wait
}

start_tts_mode() {
  if [[ "$ACCELERATOR_SELECTED" != nvidia ]]; then
    echo "ERROR: TTS GPU mode requires NVIDIA acceleration and the NVIDIA Docker runtime." >&2
    return 1
  fi
  start_control_plane
  resource_cli reconcile tts_only --wait
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
  --models)
    compose --profile models build model-downloader
    compose --profile models run --rm --no-deps model-downloader --download-all
    ;;
  --build)
    compose build
    start_asr_mode
    ;;
  --up|--asr-up)
    start_asr_mode
    ;;
  --tts-up)
    start_tts_mode
    ;;
  --down)
    stop_resource_supervisor
    compose down
    echo "GATEWAY_DOWN persistent_data_preserved=true"
    ;;
  --down_up|--restart)
    stop_resource_supervisor
    compose down
    start_asr_mode
    ;;
  --rebuild)
    stop_resource_supervisor
    compose down
    compose build --no-cache
    start_asr_mode
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
    resource_status=$(compose exec -T gateway python -c '
import json
import urllib.request
payload = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/v1/resources", timeout=3))
workloads = payload.get("workloads", {})
print("|".join((
    str(payload.get("resolved_policy", "unavailable")),
    str(payload.get("profile") or "none"),
    str(workloads.get("asr", {}).get("lifecycle", "unavailable")),
    str(workloads.get("tts", {}).get("lifecycle", "unavailable")),
)))
' 2>/dev/null || printf 'unavailable|none|unavailable|unavailable')
    IFS='|' read -r resource_policy resource_profile asr_state tts_state <<<"$resource_status"
    if [[ -z "$resource_policy" ]]; then
      resource_policy=unavailable
      resource_profile=none
      asr_state=unavailable
      tts_state=unavailable
    fi
    echo "STATUS_${health^^} web=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765} realtime=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/asr_realtime tts_clone=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/tts_clone_test docs=http://${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}/docs capture=$capture playback=$playback accelerator=$ACCELERATOR_SELECTED resource_policy=$resource_policy profile=$resource_profile asr_state=$asr_state tts_state=$tts_state asr_device=$asr_device correction_device=$correction_device"
    [[ "$health" == "healthy" ]]
    ;;
  --logs)
    logs_target=${2:-all}
    export COMPOSE_PROFILES=asr,tts
    case "$logs_target" in
      all)
        compose logs --tail 100 gateway asr-worker correction-worker tts-worker
        ;;
      gateway|asr-worker|correction-worker|tts-worker)
        compose logs --tail 100 "$logs_target"
        ;;
      *)
        echo "ERROR: logs target must be all, gateway, asr-worker, correction-worker, or tts-worker" >&2
        exit 2
        ;;
    esac
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
