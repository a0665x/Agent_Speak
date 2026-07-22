#!/usr/bin/env bash
set -euo pipefail

cd /app
mkdir -p /app/data /app/runtime/artifacts /app/models/piper "$HOME" "$HF_HOME" "$XDG_CACHE_HOME"

exec "$@"
