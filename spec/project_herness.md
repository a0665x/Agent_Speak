# Current Project State

Date: 2026-07-19

Initialized from an empty directory for Jetson AGX Orin (aarch64). ALSA sees `USB PnP Sound Device` at card 2/device 0. No speaker is connected, so TTS is validated as an audio artifact rather than physical playback.

Current implementation: Docker-first FastAPI Gateway with root `./run.sh` lifecycle control, default `/dev/snd` mapping, persistent model/data/runtime mounts, typed local providers, sessions/ordered events, bounded WAV/energy VAD, SQLite/file speaker lifecycle, bilingual accessible WebUI, and repeatable container/smoke tests. Real correction, endpoint, and external-Agent reasoning remain replaceable boundaries and must not alter client contracts.

External Agent support now includes a repository-portable Traditional Chinese Skill and an executable local stdio MCP server. MCP delegates bounded audio to the unchanged HTTP API, exposes status/capabilities, safe ALSA discovery, microphone smoke/listen once, and opt-in TTS playback. Skill is operational knowledge, MCP is control plane, and HTTP/WebSocket remain data/event planes. The external Agent performs reasoning between listen and speak.

Known MVP boundary: correction, endpoint, and the built-in Agent are explicitly deterministic development providers; the Agent is a dev echo. ASR and TTS use replaceable local inference providers. Browser formats are converted to PCM WAV before upload. Speaker similarity is deterministic convenience identification and never authentication.

Use Git history and `./scripts/status.sh` as live truth.
