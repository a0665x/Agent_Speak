# AI_Avatar — Henry GIF / Sprite Runtime Package

This folder is designed to replace the existing `AI_Avatar/` directory in:

```text
~/Desktop/Agent_Speak/AI_Avatar
```

## Package contents

- visual source sheets
- animation clip definitions
- state transition rules
- expression and viseme maps
- JSON Schemas
- event examples
- React/TypeScript interface definitions
- local-agent implementation instructions
- crop/export scripts specification

## Rendering approach

This package intentionally avoids Live2D.

The recommended flow is:

```text
VAD / ASR / LLM / TTS
        ↓
AvatarEventBus
        ↓
AvatarStateMachine
        ↓
ClipScheduler
        ↓
GifSpriteRenderer
        ↓
React WebUI
```

## Asset status

The PNG sheets under `assets/sheets/` are the source material for frame extraction.
The folders `assets/generated_frames/` and `assets/generated_gif/` are output folders for your local agent or scripts.

## Replace existing folder

```bash
cd ~/Desktop/Agent_Speak
rm -rf AI_Avatar
unzip /path/to/AI_Avatar_Henry_Complete_Pack_v3.zip
```
