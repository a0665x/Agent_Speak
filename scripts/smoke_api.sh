#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
if [[ -f "$ROOT_DIR/.env" ]]; then set -a; source "$ROOT_DIR/.env"; set +a; fi
PORT=${AGENT_SPEAK_PORT:-8765}
if [[ ! -x "$VENV_DIR/bin/python" ]]; then echo "Run ./scripts/setup.sh first." >&2; exit 1; fi
API_BASE=${API_BASE:-http://127.0.0.1:$PORT} PYTHONPATH="$ROOT_DIR/src" "$VENV_DIR/bin/python" <<'PY'
import asyncio, io, json, math, os, struct, urllib.request, wave
import websockets

base = os.environ["API_BASE"]

def call(method, path, body=None, content_type="application/json"):
    if isinstance(body, dict): body = json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=body, method=method, headers={"Content-Type": content_type})
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = response.read()
        return response.status, json.loads(payload) if payload else None

def fetch(path):
    with urllib.request.urlopen(base + path, timeout=8) as response:
        return response.status, response.headers.get_content_type(), response.read()

def tone(frequency=330):
    rate = 16000
    frames = b"".join(struct.pack("<h", int(.28 * 32767 * math.sin(2 * math.pi * frequency * i / rate))) for i in range(rate // 4))
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", "not compressed")); wav.writeframes(frames)
    return output.getvalue()

async def main():
    assert call("GET", "/api/v1/health")[1]["status"] == "ok"
    _, session = call("POST", "/api/v1/sessions", b"", "application/octet-stream")
    ws_url = base.replace("http://", "ws://").replace("https://", "wss://") + f"/api/v1/sessions/{session['id']}/events"
    async with websockets.connect(ws_url, open_timeout=5) as socket:
        first = json.loads(await asyncio.wait_for(socket.recv(), 5)); assert first["sequence"] == 1
        _, turn = await asyncio.to_thread(call, "POST", f"/api/v1/sessions/{session['id']}/turns", tone(), "audio/wav")
        events = [first]
        while events[-1]["type"] != "pipeline.completed": events.append(json.loads(await asyncio.wait_for(socket.recv(), 5)))
    assert turn["audio_url"].startswith("/api/v1/artifacts/")
    artifact_status, artifact_type, artifact = await asyncio.to_thread(fetch, turn["audio_url"])
    assert artifact_status == 200 and artifact_type == "audio/wav"
    assert artifact[:4] == b"RIFF" and artifact[8:12] == b"WAVE"
    with wave.open(io.BytesIO(artifact), "rb") as wav: assert wav.getnframes() > 0
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    _, created = call("POST", "/api/v1/speakers", {"name": "Smoke profile"})
    speaker_id = created["speaker"]["id"]
    _, enrolled = call("POST", f"/api/v1/speakers/{speaker_id}/samples", tone(), "audio/wav")
    _, matched = call("POST", "/api/v1/speakers/match", tone(), "audio/wav")
    assert enrolled["speaker"]["sample_count"] == 1 and matched["match"]["id"] == speaker_id
    status, _ = call("DELETE", f"/api/v1/speakers/{speaker_id}"); assert status == 204

asyncio.run(main())
PY
echo "API_SMOKE_OK health_session_websocket_turn_artifact_speaker_lifecycle"
