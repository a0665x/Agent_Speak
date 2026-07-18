# Architecture

## Flow
Audio enters by browser/file API or operator mic smoke. The orchestrator validates audio and executes VAD → ASR → correction → endpoint → agent → TTS. Each provider emits ordered timing events.

## Boundaries
API maps transports/errors. Pipeline owns order/timing. Providers own model behavior. Session broker owns ordered events/WebSocket fan-out. Speaker store owns profiles/samples/features. WebUI remains an API client.

## Initial providers
Energy VAD is deterministic and functional. ASR/correction/agent/TTS development providers prove integration without downloads; TTS writes a valid WAV. Capability metadata prevents development behavior being mistaken for production inference.
