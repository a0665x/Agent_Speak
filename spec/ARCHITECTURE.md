# Architecture

## Flow
Audio enters by browser/file API or operator mic smoke. The orchestrator validates audio and executes VAD → ASR → correction → endpoint → agent → TTS. Each provider emits ordered timing events.

## Boundaries
API maps transports/errors. Pipeline owns order/timing. Providers own model behavior. The ASR model manager owns the single resident provider, activation state, rollback, and one realtime lease. Session broker owns ordered events/WebSocket fan-out. Speaker store owns profiles/samples/features. WebUI remains an API client.

Presentation locale, speech inference language, and TTS voice are separate state. Realtime speech language is frozen when a session is created and copied into its stream plus ASR, endpoint, and correction jobs. Providers may select request-time language behavior but must not mutate the session or require one worker/model copy per language. See [Session-Frozen Speech Language Routing](references/lesson-20260721-session-language-routing.md).

External Agent integration uses three explicit planes. The portable Skill is operational knowledge and safety policy. The local stdio MCP server is a small control plane for status, devices, bounded capture and playback commands. Existing HTTP carries bounded WAV data and WebSocket carries ordered session events; neither contract is replaced, and raw real-time audio is never tunneled through MCP. The normal external loop is listen/ASR → external Agent reasoning → TTS/speak. The gateway's built-in Agent remains a development echo and is not external reasoning.

## Providers
Energy VAD is deterministic and functional. Realtime ASR selects exactly one resident provider: Qwen3-ASR 1.7B by default, Breeze-ASR-25 for Taiwanese Mandarin/code-switching, or Faster Whisper Small as the compact compatibility path. Device/compute mode is configured at runtime and request-time language behavior follows the frozen session policy. A model switch never mutates an active session: it closes the stream, changes the resident provider, creates a new session with frozen choices, and resumes only after readiness. Piper `zh_CN-huayan-medium` produces spoken WAV output. All production weights are prepared explicitly by the pinned `./run.sh --models` manifest; runtime inference is local-only and never downloads weights.

Realtime endpoint detection and correction can use the shared Qwen2.5 worker with bounded, language-specific prompts and conservative fallbacks. Test/degraded configurations may use transparent development adapters. The built-in Agent remains a localized development echo and must not be presented as real LLM reasoning. Stage-specific protocols keep provider replacement independent of HTTP contracts, and capability metadata is the live truth for the active provider and device.

## Audio and speakers
The API bounds bytes before WAV parsing, validates PCM structure/rate/duration, normalizes mono/stereo samples with NumPy, and computes real RMS energy. Speaker enrollment stores private WAV samples under `data/speaker_samples/` and metadata/features in SQLite. The deterministic vector uses normalized spectral bands, zero-crossing rate, and spectral centroid. Cosine similarity is for local convenience only and is not authentication.

## VoxCPM2 TTS clone boundary

The Gateway remains the only public HTTP boundary. `/api/v1/tts-clone/*` calls a private `tts-worker` over the Compose network; that worker exposes no host port, Docker socket, `/dev/snd`, or persistent voice store. The worker runs pinned VoxCPM2 through pinned vLLM-Omni on Python 3.12 and receives one optional request-scoped WAV as a data URL.

ASR/correction and VoxCPM2 are mutually exclusive GPU workloads. Operator commands stop the old inference workers before starting the new mode; the browser cannot control Docker. A clone reference is zero-shot conditioning, not LoRA or model training. Reference and generated audio remain bounded in process/browser memory and are never written as Gateway artifacts.
