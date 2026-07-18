# Current Project State

Date: 2026-07-18

Initialized from an empty directory for Jetson AGX Orin (aarch64). ALSA sees `USB PnP Sound Device` at card 2/device 0. No speaker is connected, so TTS is validated as an audio artifact rather than physical playback.

Current implementation: FastAPI contracts, typed development providers, sessions/ordered events, full-turn and stage routes, bounded WAV/energy VAD, SQLite/file speaker lifecycle, accessible WebUI, and repeatable operator/smoke scripts. Real ASR/TTS/neural-speaker engines remain replaceable providers and must not alter client contracts.

Known MVP boundary: ASR/correction/endpoint/agent/TTS are explicitly deterministic development providers. Browser formats are converted to PCM WAV before upload. Speaker similarity is deterministic convenience identification and never authentication.

Use Git history and `./scripts/status.sh` as live truth.
