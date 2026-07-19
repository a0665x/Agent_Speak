# Agent Speak

Agent Speak is a local-first Voice Agent gateway for Jetson AGX Orin: real bounded WAV decode and energy VAD feed local Faster-Whisper ASR → correction → endpoint → pluggable agent → Piper TTS providers. FastAPI exposes full-turn and separate stage APIs, ordered session events over REST/WebSocket, private speaker profiles, and a responsive browser console.

## Quick start

```sh
./scripts/setup.sh
./scripts/run.sh
```

Open `http://localhost:8765`. API docs: `http://localhost:8765/docs`.

第一次使用 API，請先閱讀 [OpenAPI 常用操作繁中快速入門](docs/OPENAPI_QUICKSTART_ZH_TW.md)。內容包含 Swagger 操作、完整語音回合、單階段 API、TTS 下載、說話者資料與常見錯誤排除。

Setup creates and uses the project `.venv`; it never installs into global Python. Copy `.env.example` to `.env` only when you need configuration overrides. Private data is created below ignored `data/` and `runtime/` paths.

The service binds to `127.0.0.1` by default. To expose it on a LAN, explicitly set `AGENT_SPEAK_HOST=0.0.0.0` only on a trusted network with appropriate host firewall controls; the MVP has no authentication or transport encryption and must not be exposed to an untrusted LAN or the public internet.

## Verify

```sh
./scripts/status.sh
./scripts/test.sh
./scripts/health_smoke.sh
./scripts/mic_smoke.sh
./scripts/smoke_api.sh
```

Run the health/API smoke scripts while `./scripts/run.sh` is active in another terminal. `mic_smoke.sh` defaults to `plughw:2,0` for a bounded three-second capture; override with `AGENT_SPEAK_MIC_DEVICE`. Every script prints an explicit `*_OK` signal on success and repair guidance on failure.

`status.sh` exits zero only when the service is running. A configured but stopped service prints `STATUS_STOPPED` and exits nonzero so monitors and shell automation can distinguish it from a healthy process.

## What the MVP does

- Accepts 8–48 kHz uncompressed 16-bit mono/stereo WAV, bounded by bytes and duration.
- Streams bounded ordered pipeline history and live stage events for each session.
- Runs local Faster-Whisper `small` ASR (Mandarin hint, CPU int8) and returns recognized speech instead of a hash placeholder.
- Generates spoken Mandarin WAV with Piper `zh_CN-huayan-medium` instead of a synthetic beep.
- Serves separate VAD, ASR, correction, endpoint, agent, and TTS stage APIs under `/api/v1`.
- Captures browser microphone audio with MediaRecorder and converts it locally to PCM WAV before upload.
- Persists speaker metadata/features in SQLite and private enrollment WAV files.

The correction, endpoint, and agent defaults remain deterministic development providers. The Agent currently returns a transparent echo response (localized for Chinese input) until an external Agent adapter is configured. Their limitations are exposed by `/api/v1/capabilities` and in the WebUI. Energy VAD, Faster-Whisper ASR, and Piper TTS perform real local inference.

Read `spec/PROJECT_MAP.md` first for architecture, API, operations, testing, UI, and model replacement details.

## Privacy

Recordings, speaker features, databases, secrets, model weights, generated audio, and agent traces are excluded from Git. Speaker matching is convenience identification, not authentication and not a security control.
