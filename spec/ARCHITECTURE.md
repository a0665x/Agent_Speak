# Architecture

## Flow
Audio enters by browser/file API or operator mic smoke. The orchestrator validates audio and executes VAD → ASR → correction → endpoint → agent → TTS. Each provider emits ordered timing events.

## Boundaries
API maps transports/errors. Pipeline owns order/timing. Providers own model behavior. Session broker owns ordered events/WebSocket fan-out. Speaker store owns profiles/samples/features. WebUI remains an API client.

## Initial providers
Energy VAD is deterministic and functional. ASR/correction/endpoint/agent/TTS development providers prove integration without downloads; deterministic TTS writes a valid 16 kHz mono WAV tone. Stage-specific protocols keep provider replacement independent of HTTP contracts. Capability metadata prevents development behavior being mistaken for production inference.

## Audio and speakers
The API bounds bytes before WAV parsing, validates PCM structure/rate/duration, normalizes mono/stereo samples with NumPy, and computes real RMS energy. Speaker enrollment stores private WAV samples under `data/speaker_samples/` and metadata/features in SQLite. The deterministic vector uses normalized spectral bands, zero-crossing rate, and spectral centroid. Cosine similarity is for local convenience only and is not authentication.
