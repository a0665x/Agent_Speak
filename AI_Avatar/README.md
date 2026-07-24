# AI Avatar — Henry Motion Package

This directory is the renderer-independent Henry asset and runtime package for
Agent Speak. The Gateway demo is available at
`http://127.0.0.1:8765/ai_avatar` after a normal frontend build.

The MVP contains six reviewed loops:

- persistent: Idle, Listening, Thinking, Speaking;
- reactions: Happy and Error.

The page is a visual motion lab. It must not activate a microphone, speaker,
ASR, Agent, or TTS. Future voice integration belongs outside the renderer and
continues to use `listen_once → external Agent reasoning/tools → speak`.

## Runtime contract

Every clip is a 512 × 512 RGBA PNG sequence aligned to `(0.5, 0.92)`. Every
clip starts and ends with the exact same shared `S0` frame,
`henry_s0`. State selection is latest selection wins:

1. the active loop continues through its final `S0`;
2. repeated clicks replace only `pendingState`;
3. after the final `S0` is displayed, the latest pending state becomes active;
4. the new loop begins from the identical `S0`.

This is why the page can change state without a crossfade, coordinate jump, or
partially interrupted gesture. Selecting the already-playing state does not
restart it.

## Directory boundaries

| Boundary | Path | Git policy |
|---|---|---|
| Source sheets | `assets/sheets/` | committed inputs |
| Reviewed geometry | `config/verified_asset_inventory.json` | committed |
| Offline providers | `.providers/` | ignored |
| Model weights | `../models/avatar_interpolation/` | ignored |
| Generated candidates/reports | `.candidates/` | ignored |
| Approved finite runtime | `public/` | committed |
| Gateway build | `../web/ai_avatar/` | committed build artifact |

Do not commit provider clones, model weights, candidate images, review reports,
logs, runtime state, recordings, or voice features.

## Rebuild assets

Provider repositories and official weights are an explicit offline setup; they
are never downloaded by the WebUI:

```bash
AI_Avatar/tools/setup_interpolation_models.sh
python AI_Avatar/tools/build_avatar_assets.py inspect
python AI_Avatar/tools/build_avatar_assets.py extract
python AI_Avatar/tools/build_avatar_assets.py review --provider auto
```

Visually inspect all previews and reports. Publish only the six current
`CLIP_ID:REPORT_SHA256` values printed by `review`, then validate:

```bash
python AI_Avatar/tools/build_avatar_assets.py publish \
  --approve idle_loop:<sha256> \
  --approve listening_loop:<sha256> \
  --approve thinking_loop:<sha256> \
  --approve speaking_loop:<sha256> \
  --approve happy_loop:<sha256> \
  --approve error_loop:<sha256>
python AI_Avatar/tools/build_avatar_assets.py validate
```

The report hash prevents stale approval after any source, crop, segmentation,
provider, or frame change. Long interpolation runs are resumable: each pair is
cached only when its input hashes, provider, and exponent still match.

## Build and verify the page

```bash
cd frontend/realtime
npm run build:avatar
npm test -- --run src/avatarLab
cd ../..
python -m pytest tests/avatar tests/test_webui.py tests/test_docker_runtime.py -q
```

See [generation workflow](docs/resource_generation_workflow.md),
[runtime architecture](docs/gif_sprite_architecture.md), and the durable
[asset-pipeline lesson](../spec/references/lesson-20260724-ai-avatar-asset-pipeline.md).
