# Current Project State

Date: 2026-07-22

Initialized from an empty directory for Jetson AGX Orin (aarch64). The 2026-07-21 status snapshot reports a healthy Gateway, NVIDIA/CUDA ASR, NVIDIA correction, and available capture/playback endpoints. This is discovery state only: no microphone capture or speaker playback was started, and `./run.sh --status` remains the live hardware truth.

Current implementation: Docker-first FastAPI Gateway with root `./run.sh` lifecycle control, generic system-default audio discovery, persistent model/data/runtime mounts, typed local providers, sessions/ordered events, bounded WAV/energy VAD, SQLite/file speaker lifecycle, an English-default `en`/`zh-TW`/`ja`/`ko` WebUI and Swagger overlay, a device-gated realtime transcription studio, and repeatable container/smoke tests. Realtime sessions freeze speech language, one of Qwen3-ASR 1.7B / Breeze-ASR-25 / Faster Whisper Small, and Qwen2.5 correction or raw ASR. One ASR provider is resident and leased at a time. Pinned weights are prepared only through `./run.sh --models`; presentation-language changes never download a language-specific model.

Realtime model switching now keeps the first user selection pending until the previous session lease is released, and reports `Ready` only after the selected ASR and runtime model agree. Breeze CUDA inputs are aligned with the model floating dtype; provider regressions cover Breeze tensor dtypes and Qwen's normalized text output. Privacy-preserving JSON Lines diagnostics are emitted to stdout and bounded rotating files for the Gateway and ASR worker. Use `./run.sh --logs [all|gateway|asr-worker|correction-worker]`; structured logs intentionally exclude audio, transcripts, device labels, credentials, request bodies, raw session IDs, and exception messages.

External Agent support now includes a repository-portable Traditional Chinese Skill and an executable local stdio MCP server. MCP delegates bounded audio to the unchanged HTTP API, exposes status/capabilities, safe ALSA discovery, microphone smoke/listen once, and opt-in TTS playback. Skill is operational knowledge, MCP is control plane, and HTTP/WebSocket remain data/event planes. The external Agent performs reasoning between listen and speak.

Known MVP boundary: active correction and endpoint behavior depends on runtime capabilities and may use the shared Qwen worker or development fallbacks. The built-in Agent is always a dev echo, not external-Agent reasoning. ASR and TTS use replaceable local inference providers. Browser formats are converted to PCM WAV before upload. Speaker similarity is deterministic convenience identification and never authentication. Presentation locale, frozen speech language, and TTS voice are independent controls.

The session-language contract and verification baseline are in [`references/lesson-20260721-session-language-routing.md`](references/lesson-20260721-session-language-routing.md). Use Git history and `./run.sh --status` as live truth.
