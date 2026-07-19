#!/usr/bin/env bash
set -euo pipefail

cd /app
mkdir -p /app/data /app/runtime/artifacts /app/models/piper "$HOME" "$HF_HOME" "$XDG_CACHE_HOME"

if [[ "${AGENT_SPEAK_SKIP_MODEL_BOOTSTRAP:-0}" != "1" ]]; then
  model_path=${AGENT_SPEAK_TTS_MODEL_PATH:-models/piper/zh_CN-huayan-medium.onnx}
  if [[ "$model_path" != /* ]]; then
    model_path="/app/$model_path"
  fi
  if [[ ! -f "$model_path" || ! -f "$model_path.json" ]]; then
    default_model=/app/models/piper/zh_CN-huayan-medium.onnx
    if [[ "$model_path" != "$default_model" ]]; then
      echo "Configured Piper model is missing: $model_path (and .json sidecar)." >&2
      exit 1
    fi
    echo "Downloading Piper zh_CN-huayan-medium model into persistent model storage..." >&2
    python -m piper.download_voices zh_CN-huayan-medium --download-dir /app/models/piper >&2
  fi
fi

exec "$@"
