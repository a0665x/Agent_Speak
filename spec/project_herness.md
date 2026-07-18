# Current Project State

Date: 2026-07-18

Initialized from an empty directory for Jetson AGX Orin (aarch64). ALSA sees `USB PnP Sound Device` at card 2/device 0. No speaker is connected, so TTS is validated as an audio artifact rather than physical playback.

Current target: API contracts, development providers, sessions/events, WAV/VAD, speaker profile lifecycle, WebUI, and repeatable smoke scripts. Real ASR/TTS/neural-speaker engines remain replaceable providers and must not alter client contracts.

Use Git history and `./scripts/status.sh` as live truth.
