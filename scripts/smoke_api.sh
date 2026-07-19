#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
cd "$ROOT_DIR"

MODE=local
if command -v docker >/dev/null 2>&1 \
  && docker compose ps --status running -q gateway 2>/dev/null | grep -q .; then
  MODE=docker
  # The Python process runs inside the Gateway network namespace, where the
  # service always listens on its internal port regardless of host publishing.
  API_BASE=http://127.0.0.1:8765
  PYTHON_RUNNER=(docker compose exec -T -e "API_BASE=$API_BASE" gateway env PYTHONPATH=/app/src python -)
else
  if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    source "$ROOT_DIR/.env"
    set +a
  fi
  PORT=${AGENT_SPEAK_PORT:-8765}
  API_BASE=${API_BASE:-http://127.0.0.1:$PORT}
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "Agent Speak is not running in Docker and the local .venv is unavailable. Run ./run.sh --build." >&2
    exit 1
  fi
  PYTHON_RUNNER=(env "API_BASE=$API_BASE" "PYTHONPATH=$ROOT_DIR/src" "$VENV_DIR/bin/python" -)
fi

"${PYTHON_RUNNER[@]}" <<'PY'
import asyncio, io, json, os, urllib.request, wave
import websockets
from agent_speak.config import Settings
from agent_speak.production import PiperTTS

base = os.environ["API_BASE"]

def call(method, path, body=None, content_type="application/json"):
    if isinstance(body, dict): body = json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=body, method=method, headers={"Content-Type": content_type})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
        return response.status, json.loads(payload) if payload else None

def fetch(path):
    with urllib.request.urlopen(base + path, timeout=60) as response:
        return response.status, response.headers.get_content_type(), response.read()

def spoken_sample():
    settings = Settings.from_env()
    return PiperTTS(model_path=settings.tts_model_path).synthesize("你好，這是語音辨識煙霧測試。")

async def main():
    sample = spoken_sample()
    assert call("GET", "/api/v1/health")[1]["status"] == "ok"
    _, session = call("POST", "/api/v1/sessions", b"", "application/octet-stream")
    ws_url = base.replace("http://", "ws://").replace("https://", "wss://") + f"/api/v1/sessions/{session['id']}/events"
    async with websockets.connect(ws_url, open_timeout=5) as socket:
        first = json.loads(await asyncio.wait_for(socket.recv(), 5)); assert first["sequence"] == 1
        _, turn = await asyncio.to_thread(call, "POST", f"/api/v1/sessions/{session['id']}/turns", sample, "audio/wav")
        events = [first]
        while events[-1]["type"] != "pipeline.completed": events.append(json.loads(await asyncio.wait_for(socket.recv(), 60)))
    assert turn["audio_url"].startswith("/api/v1/artifacts/")
    assert not turn["transcript"].startswith("Development transcript")
    assert any("\u3400" <= character <= "\u9fff" for character in turn["transcript"])
    artifact_status, artifact_type, artifact = await asyncio.to_thread(fetch, turn["audio_url"])
    assert artifact_status == 200 and artifact_type == "audio/wav"
    assert artifact[:4] == b"RIFF" and artifact[8:12] == b"WAVE"
    with wave.open(io.BytesIO(artifact), "rb") as wav: assert wav.getnframes() > 0
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    _, created = call("POST", "/api/v1/speakers", {"name": "Smoke profile"})
    speaker_id = created["speaker"]["id"]
    try:
        _, enrolled = call("POST", f"/api/v1/speakers/{speaker_id}/samples", sample, "audio/wav")
        _, matched = call("POST", "/api/v1/speakers/match", sample, "audio/wav")
        assert enrolled["speaker"]["sample_count"] == 1 and matched["match"]["id"] == speaker_id
    finally:
        status, _ = call("DELETE", f"/api/v1/speakers/{speaker_id}"); assert status == 204

asyncio.run(main())
PY

echo "API_SMOKE_OK mode=$MODE health_session_websocket_turn_artifact_speaker_lifecycle"
