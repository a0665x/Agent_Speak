#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
if [[ -f "$ROOT_DIR/.env" ]]; then set -a; source "$ROOT_DIR/.env"; set +a; fi
DEVICE=${AGENT_SPEAK_MIC_DEVICE:-plughw:2,0}
DURATION=${1:-3}
if [[ ! -x "$VENV_DIR/bin/python" ]]; then echo "Run ./scripts/setup.sh first." >&2; exit 1; fi
if ! command -v arecord >/dev/null 2>&1; then echo "arecord is required (alsa-utils)." >&2; exit 1; fi
sample=$(mktemp --suffix=.wav)
trap 'rm -f "$sample"' EXIT
if ! arecord -q -D "$DEVICE" -d "$DURATION" -f S16_LE -r 16000 -c 1 "$sample"; then
  echo "Microphone capture failed for $DEVICE. Set AGENT_SPEAK_MIC_DEVICE after checking arecord -l." >&2
  exit 1
fi
stats=$("$VENV_DIR/bin/python" - "$sample" <<'PY'
import sys, wave
import numpy as np
with wave.open(sys.argv[1], "rb") as wav:
    pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768
peak = float(np.max(np.abs(pcm))) if pcm.size else 0.0
rms = float(np.sqrt(np.mean(np.square(pcm)))) if pcm.size else 0.0
nonzero = float(np.count_nonzero(pcm) / pcm.size) if pcm.size else 0.0
print(f"peak={peak:.6f} rms={rms:.6f} nonzero_ratio={nonzero:.6f}")
assert pcm.size and peak > 0, "capture contains no signal"
PY
)
echo "MIC_SMOKE_OK device=$DEVICE duration=${DURATION}s $stats"
