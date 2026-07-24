# AI Avatar Motion Lab Design

Date: 2026-07-24

Status: Approved for implementation planning

Branch: `feature/ai-avatar-motion-lab`

## 1. Purpose

Build a renderer-independent minimum AI Avatar demo for the Henry rabbit assets.
The first release must:

- turn the existing sprite sheets into verified animation clips;
- keep the character scale, canvas, and visible-body baseline stable;
- switch states only at a completed loop boundary;
- expose the six core states in `http://127.0.0.1:8765/ai_avatar`;
- keep image generation and interpolation offline from the playback runtime;
- avoid activating the microphone, ASR, TTS, or speakers.

The MVP states are:

- `idle`
- `listening`
- `thinking`
- `speaking`
- `happy`
- `error`

## 2. Current asset finding

The existing filenames and animation manifest cannot be treated as verified
ground truth. Visual inspection found that several sheet names describe
different content from the image they contain. For example:

- `01_loop_core_idle_listening_thinking.png` is a grid of named status poses;
- `02_speaking_loops.png` is a mouth and viseme reference sheet;
- `03_reaction_happy_laugh.png` contains idle, listening, and thinking loops;
- `04_gesture_keyframes.png` contains neutral and happy speaking loops;
- `06_main_states_grid.png` contains continuous reaction and sleepy sequences.

Implementation must begin with a visual asset inventory. It must record the
actual content, grid geometry, frame ordering, and suitability of each source
sheet. Existing manifest entries are hypotheses until that inventory validates
them.

## 3. Selected approach

Use a reproducible crop-and-normalize pipeline with per-sheet configuration and
manual overrides.

Rejected as the primary approach:

- fixed-grid-only cropping, because it is brittle when sheet layouts differ;
- VLM generation for every transition, because it can drift from Henry's
  identity and produces nondeterministic assets.

The selected pipeline may detect candidate cells and character bounds
automatically, but committed configuration is the final source of truth. Model
outputs never become runtime assets until they pass validation.

## 4. Asset build pipeline

```text
Sprite sheets
    |
    v
Visual asset inventory
    |
    v
Sheet inspector
grid candidates + character bounds
    |
    v
Crop and normalize
transparent bounds + fixed canvas + shared foot anchor
    |
    v
Transition construction
shared S0 + FILM/RIFE candidates + quality gate
    |
    +--> PNG sequences
    +--> Animated WebP/GIF previews
    +--> validation report
    |
    v
Verified animation manifest
    |
    v
State machine -> clip scheduler -> canvas renderer
    |
    v
/ai_avatar
```

### 4.1 Sheet inspector

`SheetInspector` reads a per-sheet layout definition and proposes:

- cell rectangles;
- transparent or background boundaries;
- character bounding boxes;
- source frame order;
- candidate state names.

Manual configuration overrides detection. The tool must not silently infer a
new order when confidence is low.

### 4.2 Frame normalization

`FrameNormalizer` produces frames with:

- one fixed canvas size;
- one character scale policy;
- a fixed horizontal center;
- a fixed visible-body baseline at the configured anchor;
- a preserved alpha channel;
- deterministic filenames and hashes.

Playback must not resize the canvas or move the anchor when the state changes.
Because the named status sheet is waist-up while the continuous source loops
are full-body, the six-state MVP uses one reviewed waist-up composition. This
avoids scaling jumps and does not require a model to invent missing legs.

### 4.3 Export

`AnimationExporter` produces:

- a PNG sequence as the canonical runtime representation;
- Animated WebP for compact previews where supported;
- GIF as a portable review artifact;
- a machine-readable validation report.

Candidate frames, rejected interpolation output, model weights, runtime logs,
and bulk previews are local artifacts and must not be committed. The finite set
of human-approved frames required for the distributable MVP is published under
`AI_Avatar/public/` and may be committed as product artwork. Git may also
contain configuration, code, tests, small fixtures, and explicitly selected
representative previews.

## 5. Shared transition-frame contract

Every clip is a loop and must use the same canonical transition image, `S0`.

```text
S0
  -> entry transition frames
  -> core action frames
  -> exit transition frames
  -> S0
```

All clips reference the same `S0` file. They do not contain independently
rendered or copied approximations of it.

The manifest declares one global `transition_frame_id`. Validation fails unless
every clip:

- starts with that frame ID;
- ends with that frame ID;
- resolves both references to the same file and pixel hash;
- uses the same canvas, alpha format, scale, and anchor.

This contract makes the final frame of the old loop identical to the first
frame of the next loop.

## 6. Transition interpolation

Interpolation is an offline asset-build step, not part of the browser runtime.

### 6.1 Model routing

- Use RIFE as the fast path for small or moderate adjacent motion.
- Use FILM first for large motion between `S0` and a core pose.
- Request candidate frames at suitable intermediate timestamps, initially
  `0.25`, `0.50`, and `0.75`.
- Apply the same procedure in reverse from the final core pose back to `S0`.

RIFE supports arbitrary-timestep interpolation. FILM is designed for
large-motion interpolation, but neither model semantically guarantees a
correct joint angle or a plausible newly revealed body region.

References:

- <https://github.com/hzwer/ECCV2022-RIFE>
- <https://github.com/google-research/frame-interpolation>
- <https://research.google/blog/large-motion-frame-interpolation/>

### 6.2 Large-motion limitation

For an input pair such as a hand at 0 degrees and 90 degrees, an interpolation
model may produce visually useful intermediate poses. It does not operate from
a skeleton and cannot guarantee exact 30/45/60-degree geometry. Occlusion,
disocclusion, crossed limbs, ears, props, and large silhouette changes can
produce ghosting or malformed frames.

An interpolation result is therefore a candidate, not an automatically
approved asset.

### 6.3 Quality fallback

If direct interpolation fails:

1. mark the transition `needs_keyframe`;
2. keep it out of the ready manifest;
3. add a human-reviewed intermediate keyframe;
4. interpolate the shorter segments separately;
5. rerun validation and visual review.

A failed model result must never be silently substituted into a ready clip.

## 7. Quality gates

`ManifestValidator` and the asset validator check:

- shared `S0` identity and pixel hash;
- file existence and frame count;
- fixed canvas dimensions and alpha format;
- fixed visible-body baseline and bounded center/scale drift;
- unexpected transparent-boundary growth;
- excessive difference between adjacent frames;
- duplicate, missing, or reordered frames;
- model/provider metadata for generated candidates;
- explicit `approved`, `needs_review`, or `needs_keyframe` status.

Only `approved` clips are exposed as Ready in the demo.

Automated metrics are a screening mechanism. A contact sheet or animated
preview remains part of approval because perceptual defects cannot be fully
reduced to one numeric threshold.

## 8. Runtime architecture

The runtime retains the module boundaries required by `AI_Avatar/AGENTS.md`:

- `EventBus`
- `AvatarStateMachine`
- `ClipScheduler`
- `Renderer`
- `VisemeController`
- `StateTransitionController`

The MVP implements only the behavior required by the six visual states.
Viseme and voice-pipeline integration remain provider boundaries and are not
wired to ASR or TTS in this release.

### 8.1 State scheduling

The scheduler stores:

- `playingState`
- `pendingState`
- current clip and frame
- preload/readiness state

When a user selects a different state:

1. keep playing the current loop;
2. replace `pendingState` with the latest selected state;
3. ignore older pending selections;
4. reach the current clip's final shared `S0`;
5. start the pending clip at its first shared `S0`;
6. clear `pendingState`.

Selecting the currently playing state does not restart or enqueue it. If the
pending clip fails to load, the current clip continues looping and the error is
reported.

No crossfade is required at the clip boundary because both boundary frames are
the same pixels. Crossfade must not be used to hide a failed shared-frame
contract.

## 9. Web UI

The Gateway serves the demo at:

`http://127.0.0.1:8765/ai_avatar`

The page contains:

- a fixed-size canvas stage for Henry;
- grouped state controls;
- persistent-state buttons for Idle, Listening, Thinking, and Speaking;
- reaction-state buttons for Happy and Error;
- Pause and Restart playback controls;
- Ready, Playing, and Queued indicators;
- a collapsible development panel showing clip, frame, FPS, loop, anchor,
  preload, source, and quality status.

All six MVP states are loops. Happy and Error continue until another state is
selected.

Buttons remain disabled until the manifest is valid and required clips are
preloaded. Keyboard focus, reduced-motion preferences, loading, unavailable,
and error states are required.

Opening the page must not request microphone permission or activate audio
capture, ASR, TTS, or speaker playback.

## 10. Error handling

- Invalid manifest: show a blocking asset-validation error.
- Clip preload failure: keep the current loop and mark the target unavailable.
- Interpolation failure: mark `needs_keyframe`; do not publish the candidate.
- Renderer failure: retain the last valid frame and expose diagnostic context.
- Missing model weight: skip interpolation with an actionable offline setup
  message; do not download weights during normal WebUI startup.
- Unsupported Animated WebP: use the canonical PNG sequence renderer.

Diagnostics must identify the sheet, clip, source frame pair, provider,
validation rule, and artifact path without logging private Agent state.

## 11. Test strategy

Behavior changes follow test-driven development.

### 11.1 Asset and manifest tests

- inventory records match source files;
- crop geometry remains within source bounds;
- normalized frames have identical canvas and anchor rules;
- all clip first/last frame IDs resolve to the global `S0`;
- first/last pixel hashes are identical;
- invalid interpolation candidates cannot become Ready;
- missing files, duplicate frames, and incorrect ordering fail validation.

### 11.2 Scheduler tests

- one selection waits for the current loop boundary;
- repeated selections retain only the latest pending state;
- selecting the active state does not restart it;
- the handoff satisfies `old.last === S0 === new.first`;
- failed target preload leaves the current loop active.

### 11.3 UI tests

- `/ai_avatar` is served by the Gateway;
- all six state controls are present and keyboard accessible;
- controls remain disabled until preload and validation succeed;
- Playing, Queued, frame, FPS, and quality status remain synchronized;
- canvas size and character anchor do not change across states;
- page load does not activate any audio device or voice provider.

### 11.4 Verification

Run the existing repository baseline plus the new avatar tests. Browser review
must include an animated transition through each state and a rapid-click case
that demonstrates latest-selection-wins behavior.

## 12. Documentation plan

Before runtime implementation:

1. produce a visually verified asset inventory;
2. correct misleading sheet/manifest documentation without destroying source
   provenance;
3. make `AI_Avatar/README.md` the task-oriented entry point;
4. separate source-generation guidance from runtime architecture;
5. document the `S0` contract and interpolation quality workflow;
6. link the avatar design from `spec/PROJECT_MAP.md`.

The implementation plan will be written only after this design has been
reviewed.

## 13. Delivery stages

1. Design spec and project index.
2. Verified asset inventory and corrected documentation.
3. Crop, normalize, interpolation, export, and validation pipeline.
4. State machine, latest-selection scheduler, and canvas renderer.
5. Gateway `/ai_avatar` MVP.
6. Automated verification and representative screenshots/previews.

## 14. Deferred scope

- microphone, ASR, Agent, TTS, and speaker integration;
- viseme-driven mouth animation;
- runtime model inference;
- VLM-generated transitions;
- automatic approval of generated frames;
- additional states beyond the six MVP states;
- user-uploaded avatar or biometric assets.
