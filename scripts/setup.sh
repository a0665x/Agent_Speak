#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN=${PYTHON_BIN:-python3.11}
cd "$ROOT_DIR"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.11 is required. Set PYTHON_BIN to its executable." >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv "$VENV_DIR" --python "$PYTHON_BIN"
  else
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
fi

if ! "$VENV_DIR/bin/python" -c 'import dotenv, fastapi, faster_whisper, httpx, mcp, numpy, piper, pytest, uvicorn, websockets' >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    (cd "$ROOT_DIR" && uv pip install --python "$VENV_DIR/bin/python" -e '.[test]')
  else
    (cd "$ROOT_DIR" && "$VENV_DIR/bin/python" -m pip install -e '.[test]')
  fi
fi

DEFAULT_PIPER_MODEL="$ROOT_DIR/models/piper/zh_CN-huayan-medium.onnx"
CONFIGURED_PIPER_MODEL=${AGENT_SPEAK_TTS_MODEL_PATH:-$DEFAULT_PIPER_MODEL}
if [[ "$CONFIGURED_PIPER_MODEL" != /* ]]; then
  CONFIGURED_PIPER_MODEL="$ROOT_DIR/$CONFIGURED_PIPER_MODEL"
fi
if [[ ! -f "$CONFIGURED_PIPER_MODEL" || ! -f "$CONFIGURED_PIPER_MODEL.json" ]]; then
  if [[ "$CONFIGURED_PIPER_MODEL" != "$DEFAULT_PIPER_MODEL" ]]; then
    echo "Configured Piper model is missing: $CONFIGURED_PIPER_MODEL (and .json sidecar)." >&2
    exit 1
  fi
  mkdir -p "$(dirname "$DEFAULT_PIPER_MODEL")"
  "$VENV_DIR/bin/python" -m piper.download_voices zh_CN-huayan-medium --download-dir "$(dirname "$DEFAULT_PIPER_MODEL")"
fi

PYTHONPATH="$ROOT_DIR/src" "$VENV_DIR/bin/python" -c 'from agent_speak.app import create_app; assert create_app().title == "Agent Speak"'
echo "SETUP_OK python=$($VENV_DIR/bin/python --version 2>&1) venv=$VENV_DIR"
