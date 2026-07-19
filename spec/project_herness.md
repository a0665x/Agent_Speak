# Current Project State

Date: 2026-07-19

Initialized from an empty directory for Jetson AGX Orin (aarch64). ALSA sees `USB PnP Sound Device` at card 2/device 0. No speaker is connected, so TTS is validated as an audio artifact rather than physical playback.

Current implementation: FastAPI contracts, typed development providers, sessions/ordered events, full-turn and stage routes, bounded WAV/energy VAD, SQLite/file speaker lifecycle, accessible WebUI, and repeatable operator/smoke scripts. Real ASR/TTS/neural-speaker engines remain replaceable providers and must not alter client contracts.

External Agent support now includes a repository-portable Traditional Chinese Skill and an executable local stdio MCP server. MCP delegates bounded audio to the unchanged HTTP API, exposes status/capabilities, safe ALSA discovery, microphone smoke/listen once, and opt-in TTS playback. Skill is operational knowledge, MCP is control plane, and HTTP/WebSocket remain data/event planes. The external Agent performs reasoning between listen and speak.

Known MVP boundary: correction, endpoint, and the built-in Agent are explicitly deterministic development providers; the Agent is a dev echo. ASR and TTS use replaceable local inference providers. Browser formats are converted to PCM WAV before upload. Speaker similarity is deterministic convenience identification and never authentication.

Use Git history and `./scripts/status.sh` as live truth.
