# Architecture

## Flow
Audio enters by browser/file API or operator mic smoke. The orchestrator validates audio and executes VAD → ASR → correction → endpoint → agent → TTS. Each provider emits ordered timing events.

## Boundaries
API maps transports/errors. Pipeline owns order/timing. Providers own model behavior. Session broker owns ordered events/WebSocket fan-out. Speaker store owns profiles/samples/features. WebUI remains an API client.

External Agent integration uses three explicit planes. The portable Skill is operational knowledge and safety policy. The local stdio MCP server is a small control plane for status, devices, bounded capture and playback commands. Existing HTTP carries bounded WAV data and WebSocket carries ordered session events; neither contract is replaced, and raw real-time audio is never tunneled through MCP. The normal external loop is listen/ASR → external Agent reasoning → TTS/speak. The gateway's built-in Agent remains a development echo and is not external reasoning.

## Initial providers
Energy VAD is deterministic and functional. The default speech path now uses local Faster-Whisper `small` on CPU/int8 with a Mandarin language hint, and Piper `zh_CN-huayan-medium` for spoken WAV output. Both models load lazily. `scripts/setup.sh` installs the provider packages and downloads the ignored Piper voice files; Faster-Whisper uses the Hugging Face cache. Correction, endpoint, and Agent are still transparent development adapters, and the Agent returns a localized echo rather than pretending to be an LLM. Stage-specific protocols keep provider replacement independent of HTTP contracts. Capability metadata distinguishes real inference from remaining development behavior.

## Audio and speakers
The API bounds bytes before WAV parsing, validates PCM structure/rate/duration, normalizes mono/stereo samples with NumPy, and computes real RMS energy. Speaker enrollment stores private WAV samples under `data/speaker_samples/` and metadata/features in SQLite. The deterministic vector uses normalized spectral bands, zero-crossing rate, and spectral centroid. Cosine similarity is for local convenience only and is not authentication.
