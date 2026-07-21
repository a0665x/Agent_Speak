# Current Project State

Date: 2026-07-21

Initialized from an empty directory for Jetson AGX Orin (aarch64). The 2026-07-21 status snapshot reports a healthy Gateway, NVIDIA/CUDA ASR, NVIDIA correction, and available capture/playback endpoints. This is discovery state only: no microphone capture or speaker playback was started, and `./run.sh --status` remains the live hardware truth.

Current implementation: Docker-first FastAPI Gateway with root `./run.sh` lifecycle control, default `/dev/snd` mapping, persistent model/data/runtime mounts, typed local providers, sessions/ordered events, bounded WAV/energy VAD, SQLite/file speaker lifecycle, an English-default `en`/`zh-TW`/`ja`/`ko` WebUI and Swagger overlay, a device-gated realtime transcription studio, and repeatable container/smoke tests. Realtime sessions freeze one of `auto`, `en`, `zh-TW`, `ja`, or `ko` and route it through shared Faster-Whisper and Qwen inference without per-language model downloads.

External Agent support now includes a repository-portable Traditional Chinese Skill and an executable local stdio MCP server. MCP delegates bounded audio to the unchanged HTTP API, exposes status/capabilities, safe ALSA discovery, microphone smoke/listen once, and opt-in TTS playback. Skill is operational knowledge, MCP is control plane, and HTTP/WebSocket remain data/event planes. The external Agent performs reasoning between listen and speak.

Known MVP boundary: active correction and endpoint behavior depends on runtime capabilities and may use the shared Qwen worker or development fallbacks. The built-in Agent is always a dev echo, not external-Agent reasoning. ASR and TTS use replaceable local inference providers. Browser formats are converted to PCM WAV before upload. Speaker similarity is deterministic convenience identification and never authentication. Presentation locale, frozen speech language, and TTS voice are independent controls.

The session-language contract and verification baseline are in [`references/lesson-20260721-session-language-routing.md`](references/lesson-20260721-session-language-routing.md). Use Git history and `./run.sh --status` as live truth.
