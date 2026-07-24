# Henry PNG Sequence Architecture

The filename is retained for compatibility, but the approved runtime does not
switch raw GIF files. It renders deterministic RGBA PNG sequences.

## Portable boundaries

```text
UI state button
    ↓
StateTransitionController
    ↓
AvatarStateMachine (playingState + pendingState)
    ↓
ClipScheduler (FPS + loop boundary)
    ↓
PngSequenceRenderer (fixed 512 × 512 Canvas)
```

`EventBus` carries typed selection, loop-complete, and renderer-failure
notifications. `VisemeController` is a deliberately disabled port in this MVP;
the motion lab is not coupled to ASR or TTS.

## Manifest v4

`public/manifest.json` owns:

- one immutable `transition_frame_id`;
- a SHA-256 and project-relative source for each approved frame;
- exactly six approved loop clips;
- fixed viewport and anchor metadata;
- per-clip FPS and ordered frame IDs.

Browser parsing rejects unknown states, traversal paths, missing frames,
unapproved clips, and any clip whose first or final frame is not shared `S0`.
All unique images decode before the UI reports **Assets Ready**.

## Boundary scheduling

The scheduler never cuts a gesture mid-loop. A state click only replaces the
pending state. The old clip displays its final shared `S0`, emits
`loop.completed`, and then promotes the latest pending state. Because the new
clip begins with the byte-identical `S0`, no crossfade is needed.

If a target clip cannot preload, that state becomes unavailable without
interrupting the active loop. Selecting the active state is a no-op.

## Rendering

`PngSequenceRenderer` accepts only preloaded frame IDs. Canvas size never
changes between clips. A frame is drawn with copy compositing so transparent
pixels replace the previous image atomically. A failed draw retains the last
successful frame and emits `renderer.failed`.

Pause stops animation scheduling. Resume preserves the current frame. Restart
returns the active clip to its first `S0` and clears pending selection.
Disposal cancels `requestAnimationFrame` and releases image references.
