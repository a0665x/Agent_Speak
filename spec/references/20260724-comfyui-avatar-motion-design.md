# ComfyUI FLF2V AI Avatar Motion Design

**Date:** 2026-07-24
**Branch:** `feature/ai-avatar-motion-lab`
**Status:** Approved; ComfyUI FLF2V is the only planned generative motion path

## Decision

New AI Avatar motions use ComfyUI first-last-frame-to-video (FLF2V). The same
reviewed shared transition frame, `S0`, is supplied as both the first and last
conditioning image. A motion prompt describes the action between those
boundaries, such as breathing, scratching the head, nodding, looking around,
or shaking the head.

The GPT Image rig, skeleton, pose-map, per-keyframe generation, and
anchored-neighbor workflow are abandoned. They must not be reintroduced as an
implicit fallback. This avoids repeated paid image requests, per-frame token
cost, slow human review, and identity drift across independently generated
stills.

Google FILM and RIFE remain available as deterministic post-processing tools
for frame-rate conversion, short transition repair, or interpolation between
already approved neighboring frames. They are not the primary semantic motion
generator.

## Goals

- Generate a complete short motion from one reviewed character S0 and a prompt.
- Preserve the existing exact shared-S0 loop switching contract.
- Keep ComfyUI, workflow models, and generation offline from browser playback.
- Accept local or remote ComfyUI deployments without coupling runtime to one
  GPU, model checkpoint, or custom-node installation.
- Preserve generated GIF, Animated WebP, WebM, or MP4 for review.
- Publish only deterministic RGBA PNG sequences to the current
  `ClipScheduler`.
- Keep model weights, generated media, queue history, logs, and review data out
  of Git.

## Non-goals

- No GPT Image API or per-frame paid generation.
- No skeleton/ControlNet rig authoring in the first ComfyUI implementation.
- No ComfyUI dependency during Gateway or `/ai_avatar` startup.
- No automatic publication based only on model completion.
- No direct GIF timing as the loop-boundary clock.
- No automatic FLF2V checkpoint download during normal `run.sh --up`.

## Existing runtime boundary

The current six-state demo consumes fixed-canvas PNG sequences for `idle`,
`listening`, `thinking`, `speaking`, `happy`, and `error`. Every loop begins
and ends with the same `henry_s0` frame ID and pixel hash. The scheduler
finishes the active loop, displays its final S0, then starts the latest pending
state from the identical S0.

ComfyUI changes only how future candidate motion frames are authored. It does
not change `AvatarStateMachine`, `ClipScheduler`, `PngSequenceRenderer`, or the
event contract.

## Architecture

```text
Reviewed character S0
        |
        +---------------------------+
        |                           |
        v                           v
ComfyUI first image            ComfyUI last image
        |                           |
        +------------ S0 -----------+
                     |
             motion preset/prompt
                     |
                     v
        reviewed FLF2V workflow JSON
                     |
                     v
          external ComfyUI provider
                     |
          GIF / WebP / WebM / MP4
                     |
                     v
       fixed-FPS decode and alpha matte
                     |
          exact S0 boundary replace
                     |
    S0→frame 2 / penultimate→S0 quality gate
                     |
        optional FILM/RIFE local repair
                     |
                     v
        reviewed RGBA PNG candidate clip
                     |
          existing hash-bound publisher
                     |
                     v
            current loop scheduler
```

## Official workflow baseline

The adapter targets a generic first-last-frame contract rather than one
hard-coded checkpoint. Review templates in this order:

1. Wan2.2 14B FLF2V when deployment VRAM and storage allow it;
2. Wan2.1 14B FLF2V as a compatible fallback;
3. another FLF2V workflow only when it provides explicit first/last image
   inputs and a deterministic output node.

Official references:

- [ComfyUI Wan2.2 First-Last-Frame to Video](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [ComfyUI Wan2.1 First-Last-Frame to Video](https://docs.comfy.org/tutorials/video/wan/wan-flf)
- [ComfyUI `WanFirstLastFrameToVideo` node](https://docs.comfy.org/built-in-nodes/WanFirstLastFrameToVideo)
- [Official ComfyUI workflow templates](https://github.com/Comfy-Org/workflow_templates)

Model choice is deployment configuration. The repository stores only
sanitized workflow JSON, schemas, and motion presets; never checkpoints.

## Asset layout

```text
AI_Avatar/assets/
├── reference/
│   └── <character>.png
└── comfyui_assets/
    ├── workflows/
    │   └── <reviewed-flf2v-workflow>.json
    ├── motion-presets/
    │   ├── breathing.json
    │   ├── scratch_head.json
    │   └── head_shake.json
    └── schemas/
        ├── comfyui-motion.schema.json
        └── comfyui-workflow-binding.schema.json

AI_Avatar/.candidates/comfyui/
└── <character>/<motion>/<job-id>/
    ├── job.json
    ├── source.json
    ├── preview/
    ├── decoded/
    ├── rgba/
    ├── frames/
    ├── reports/
    └── approvals.json
```

The second tree is ignored. Workflow JSON is committed only after removing
absolute paths, credentials, machine queue data, and private outputs.

## Motion preset contract

```json
{
  "version": "1.0",
  "motion_id": "breathing",
  "character_id": "henry",
  "workflow_id": "wan2_2_flf2v_14b",
  "first_frame_id": "henry_s0",
  "last_frame_id": "henry_s0",
  "prompt": "Henry breathes gently while both feet and clothing stay fixed.",
  "negative_prompt": "camera motion, background motion, extra limbs, text",
  "width": 512,
  "height": 512,
  "fps": 12,
  "duration_seconds": 3,
  "seed": 42,
  "output_node_id": "save_video"
}
```

Validation rejects unsafe IDs, different first/last frame IDs, unsupported
outputs, absolute paths, credentials, queue data, and unknown binding slots.

## Provider boundary

`ComfyUiProvider` owns capability checks, S0 upload/binding to both inputs,
substitution into declared workflow slots, `/prompt` submission, polling only
the returned prompt ID, retrieving only the declared output, bounded timeout,
cancellation, and sanitized diagnostics.

Its result contains only prompt ID, workflow hash, seed, elapsed time, media
type, and a relative preview path. It must not store authorization data, full
queue/history responses, signed URLs, absolute machine paths, server secrets,
or model weights. It has no publication authority.

## S0 and alpha contract

Identical first/last conditioning images do not prove a seamless loop. FLF2V
may still change pose, lighting, background, silhouette, or identity near the
boundary.

Normalization must:

1. decode source media to configured fixed FPS and canvas;
2. composite S0 over one flat chroma background before generation when the
   workflow cannot preserve alpha;
3. matte every decoded frame back to RGBA with soft edges and despill;
4. replace decoded frame zero and final frame with exact reviewed S0 bytes;
5. compare `S0 → frame 2` and `penultimate frame → S0`;
6. reject a visible jump or route bounded repair through FILM/RIFE;
7. retain original media only as an ignored review preview.

Production consumes normalized PNGs. GIF/WebP may be previewed but cannot be
the precise state-transition clock.

## FILM/RIFE role

The existing Google FILM and RIFE providers may:

- resample approved video to target FPS;
- repair a short boundary when the semantic pose is already valid;
- add frames between approved adjacent images;
- provide offline quality comparison.

They must not invent a missing large semantic action. When FLF2V produces the
wrong motion or anatomy, regenerate or change the prompt/workflow.

## Resource policy

- ComfyUI may run locally or on a configured LAN GPU host.
- URL and authentication come from environment/deployment configuration.
- Normal startup does not download or load FLF2V weights.
- Low-memory devices may author remotely and play final PNGs locally.
- Runtime playback requires no ComfyUI process or video model in memory.

## Review and publication

Automatic checks cover exact frame count/FPS/canvas/RGBA, exact S0 boundaries,
alpha coverage, center/baseline/scale/silhouette drift, detached anatomy,
adjacent deltas, both S0 neighbors, and all workflow/source/output hashes.

A clean result remains `needs_review`. A reviewer confirms identity, anatomy,
clothing, intended action, background stability, loop continuity, and no
camera motion. Publication requires the existing current report hash. The
candidate generator cannot write `AI_Avatar/public/`.

## Tests

The offline suite covers strict schemas, workflow sanitization, safe binding,
mocked submit/poll/timeout/cancel/download, deterministic fixed-FPS extraction,
exact S0 bytes, S0-neighbor jump rejection, alpha checks, no preview
publication, no live ComfyUI dependency, and unchanged current scheduler/loops.

One opt-in integration test may target a configured server. It prints server
and workflow hash before submission, remains disabled in default CI, and never
auto-publishes.

## Migration and success

- GPT Image design, plan, provider, skill, tests, and candidates are removed.
- Current sheet-derived clips and FILM/RIFE configuration remain unchanged.
- Future motion authoring enters only through `comfyui_assets`.
- Runtime manifest changes only after a candidate passes automatic and human
  gates.
- Future agents find this spec from `spec/PROJECT_MAP.md`.
- No active project spec instructs agents to build GPT Image avatar motion.
- Existing `/ai_avatar` behavior remains regression-safe.

