# Voice Agent Platform MVP Design

## Decision
Build a modular local-first FastAPI service with a dependency-light HTML/CSS/JS operator console. Every speech stage is an explicit provider boundary, with full-turn and stage-level APIs. It runs without large downloads through deterministic development providers, while real VAD and microphone capture work immediately.

## Considered approaches
1. Monolithic model server: quick demo, but model failures couple the product.
2. Modular in-process pipeline (chosen): low overhead, typed replaceable providers.
3. Distributed model services: strong isolation but excessive first-release complexity and latency.

## Architecture
VAD → ASR → correction → end detection → agent → TTS. Sessions emit ordered events and latency metrics. REST handles commands/artifacts; WebSocket streams events. SQLite stores metadata; ignored runtime paths store private audio/features.

## Boundaries
Browser MediaRecorder uploads turns. Server mic smoke uses ALSA. MVP speaker matching uses deterministic acoustic features and is not biometric authentication. TTS produces a valid WAV artifact because no speaker is connected. Agent defaults to a local development adapter and can be replaced by an OpenAI-compatible client.

## UI
Warm-white, single-accent operator console with recording control, pipeline rail, transcript/response, latency, provider capability and speaker profile views. Mobile, keyboard, reduced-motion, loading, empty, and error states are required.

## Testing and privacy
TDD covers contracts, events, WAV/VAD, speaker lifecycle, adapters, and endpoints. Verification includes pytest, API smoke, bounded USB-mic capture, and desktop/mobile browser smoke. Secrets, voice data, embeddings, weights, generated audio, and traces never enter Git.
