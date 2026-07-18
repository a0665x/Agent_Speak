# Agent Speak

Local-first Voice Agent gateway for Jetson AGX Orin: VAD → ASR → correction → endpoint detection → arbitrary Agent → TTS, with session events, speaker profiles, and a responsive operator console.

## Quick start

```sh
./scripts/setup.sh
./scripts/run.sh
```

Open `http://localhost:8765`. API docs: `http://localhost:8765/docs`.

## Verify

```sh
./scripts/test.sh
./scripts/mic_smoke.sh
./scripts/smoke_api.sh
```

The default ASR/Agent/TTS adapters are explicit offline development providers, not production models. Read `spec/PROJECT_MAP.md` first for architecture, APIs, operations, testing, and model replacement strategy.

## Privacy

Recordings, speaker features, databases, secrets, model weights, generated audio, and agent traces are excluded from Git. Speaker matching is convenience identification, not authentication.
