#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${AGENT_SPEAK_SCREENSHOT_URL:-http://127.0.0.1:8765}"
CHROME_BIN="${CHROME_BIN:-$(command -v google-chrome || true)}"
FFMPEG_BIN="${FFMPEG_BIN:-$(command -v ffmpeg || true)}"
OUTPUT_DIR="${ROOT_DIR}/docs/screenshots"
TEMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

if [[ -z "${CHROME_BIN}" ]]; then
  echo "ERROR: google-chrome is required" >&2
  exit 1
fi
if [[ -z "${FFMPEG_BIN}" ]]; then
  echo "ERROR: ffmpeg is required" >&2
  exit 1
fi
if ! curl --fail --silent --show-error "${BASE_URL}/api/v1/health" >/dev/null; then
  echo "ERROR: Agent Speak is not reachable at ${BASE_URL}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

capture_page() {
  local output_path="$1"
  local url="$2"
  local wait_ms="${3:-3500}"
  local height="${4:-900}"
  local profile_dir="${TEMP_DIR}/chrome-$(basename "${output_path%.png}")"

  "${CHROME_BIN}" \
    --headless=new \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-extensions \
    --disable-features=Translate \
    --force-device-scale-factor=1 \
    --hide-scrollbars \
    --window-size="1440,${height}" \
    --virtual-time-budget="${wait_ms}" \
    --user-data-dir="${profile_dir}" \
    --screenshot="${output_path}" \
    "${url}"
}

crop_page() {
  local source="$1"
  local offset_y="$2"
  local filename="$3"

  "${FFMPEG_BIN}" -hide_banner -loglevel error -y -i "${source}" \
    -vf "crop=1440:900:0:${offset_y}" "${OUTPUT_DIR}/${filename}"
}

# These visits are intentionally read-only. Never grant media permissions or
# trigger the device-check/listening controls from this documentation workflow.
capture_page "${TEMP_DIR}/project-home-full.png" "${BASE_URL}/?lang=en" 3500 2200
crop_page "${TEMP_DIR}/project-home-full.png" 0 "01-project-home-hero.png"
crop_page "${TEMP_DIR}/project-home-full.png" 600 "02-project-home-destinations.png"
crop_page "${TEMP_DIR}/project-home-full.png" 1050 "03-project-home-pipeline.png"

capture_page "${TEMP_DIR}/asr-realtime-full.png" "${BASE_URL}/asr_realtime?lang=en" 3500 2300
crop_page "${TEMP_DIR}/asr-realtime-full.png" 220 "04-asr-realtime-device-gate.png"
crop_page "${TEMP_DIR}/asr-realtime-full.png" 560 "05-asr-realtime-process-cycle.png"
crop_page "${TEMP_DIR}/asr-realtime-full.png" 1000 "06-asr-realtime-transcript.png"
crop_page "${TEMP_DIR}/asr-realtime-full.png" 1320 "07-asr-realtime-utterance-graph.png"

capture_page "${OUTPUT_DIR}/08-api-explorer.png" "${BASE_URL}/docs?lang=en" 7000

"${FFMPEG_BIN}" -hide_banner -loglevel error -y \
  -framerate 0.4 -pattern_type glob -i "${OUTPUT_DIR}/0*.png" \
  -vf "fps=10,scale=960:-1:flags=lanczos,split[frames][palette_source];[palette_source]palettegen=max_colors=128[palette];[frames][palette]paletteuse=dither=bayer" \
  -loop 0 "${OUTPUT_DIR}/agent-speak-tour.gif"

echo "SCREENSHOTS_READY path=${OUTPUT_DIR}"
