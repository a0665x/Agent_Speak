# AGENTS.md — Henry Avatar Local Agent Instructions

## Mission

Implement a renderer-independent Henry avatar runtime using GIF, Animated WebP, or PNG frame sequences.

## Read order

1. `README.md`
2. `docs/design_Henry_AI_Avatar.md`
3. `docs/gif_sprite_architecture.md`
4. `config/animation_manifest.json`
5. `config/state_transition_map.json`
6. `data/asset_index.json`
7. `schemas/*.schema.json`

## Required modules

- AvatarEventBus
- AvatarStateMachine
- ClipScheduler
- GifSpriteRenderer
- VisemeController
- StateTransitionController

## Rules

- Do not directly couple ASR/TTS code to image elements.
- Only allow clip IDs declared in `config/animation_manifest.json`.
- Persistent states use loop clips.
- Reactions use once clips and then return to the active persistent state.
- Preserve one common anchor position for all rendered clips.
- Prevent layout shift by using one fixed viewport size.
- Preload the next clip before switching.
- Do not rely on `onLoad` alone for GIF completion; use manifest duration or PNG sequence playback.
- Prefer PNG sequence or Animated WebP over GIF when precise completion timing is required.

## First milestone

1. Parse and validate all JSON files.
2. Implement the TypeScript interfaces in `frontend/types/avatar.ts`.
3. Implement the clip scheduler.
4. Create a React component that displays the active clip.
5. Add event mapping for VAD, ASR, LLM, and TTS.
6. Add tests for state transitions and one-shot return behavior.
