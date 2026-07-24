# GPT Image Character Motion Skill Design

**Date:** 2026-07-24
**Branch:** `feature/ai-avatar-motion-lab`
**Status:** Approved design with dual asset-generation amendment;
implementation not started

## Goal

Add a project-local skill that turns a reviewed full-body character reference
into a reproducible rig, deterministic skeleton pose maps, and staged
GPT Image flesh keyframes. Prove the workflow with one three-second Henry
scratch-head loop without replacing the six existing runtime loops.

The skill must generalize from `AI_Avatar/assets/reference/*.png`; it must not
hard-code Henry's anatomy, identity, or motion into the runner.

The asset pipeline must also reserve a second provider path named
`comfyui_assets`. That path accepts first-last-frame video workflows such as
ComfyUI FLF2V, with the exact same approved S0 supplied at both boundaries and
a motion prompt describing the middle of the loop. Both paths converge on one
review, normalization, and publication contract.

## Selected decisions

- Deliver a reusable skill plus one Henry scratch-head proof loop.
- Use GPT Image rather than downloading a local ControlNet model in this phase.
- Infer a structured rig once, review it, and draw skeleton PNGs
  deterministically from `rig.json`.
- Generate flesh keyframes with an anchored-neighbor topology:
  canonical reference + current pose map + nearest approved frame.
- Convert GPT Image 2's opaque output to RGBA through one flat chroma
  background, soft matting, despill, and edge validation.
- Review and approve one keyframe before unlocking the next.
- Preserve an exact shared S0 file at the beginning and end of every loop.
- Keep all generated outputs as ignored candidates until their exact hashes
  pass automatic gates and human review.
- Keep two independent candidate-generation paths:
  `gpt_image_assets` for reviewed pose/keyframe generation and
  `comfyui_assets` for first-last-frame video generation.
- Preserve the original ComfyUI GIF, Animated WebP, or video as a review
  preview, but normalize approved output into a deterministic PNG frame
  sequence before connecting it to the precise runtime scheduler.
- Require both generation paths to publish through the same manifest,
  shared-S0, geometry, temporal, identity, and approval gates.

## OpenAI capability boundary

The official Image API supports image generation and edits with one or more
reference images. GPT Image 2 processes reference images at high fidelity and
supports edit masks. The documented API does not expose a ControlNet tensor,
pose weight, or joint constraint parameter. GPT Image's public limitations also
include occasional recurring-character inconsistency and imprecise structured
composition.

GPT Image 2 does not support transparent output. This design therefore treats
the skeleton image as a strong visual instruction, not a hard latent
constraint, and enforces geometry after generation.

Source:
[OpenAI Image Generation Guide](https://developers.openai.com/api/docs/guides/image-generation)

The implementation must not claim that a visual skeleton reference is
equivalent to ControlNet.

## Dual asset-generation architecture

The two paths solve different motion-authoring problems.

### `gpt_image_assets`

Use this path when the motion needs explicit reviewed semantic poses or a
stable character rig. It creates deterministic pose maps and advances one
flesh keyframe at a time through the anchored-neighbor review topology.

This remains the selected path for the first Henry scratch-head proof because
the proof is intended to validate rig stability, stage gating, and identity
review.

### `comfyui_assets`

Use this path when the approved S0 already exists and the desired motion is
best described as a continuous short loop, such as breathing, scratching the
head, looking around, nodding, or shaking the head.

The adapter supplies the exact approved S0 as both the first and last input
frame, together with the motion prompt and reproducibility parameters.
ComfyUI's official Wan FLF2V workflows are designed to generate intermediate
frames between start and end images. The provider is deliberately generic so
a reviewed FLF2V workflow can be upgraded without coupling the avatar runtime
to one model implementation.

Sources:

- [ComfyUI Wan2.1 First-Last-Frame to Video](https://docs.comfy.org/tutorials/video/wan/wan-flf)
- [ComfyUI Wan2.2 First-Last-Frame to Video](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [ComfyUI `WanFirstLastFrameToVideo` node](https://docs.comfy.org/built-in-nodes/WanFirstLastFrameToVideo)

FLF2V is a candidate generator, not a publication authority. Supplying S0 at
both inputs improves loop conditioning but does not prove a seamless boundary.
The extracted second and penultimate frames must still pass temporal checks
against exact S0.

### Converged output contract

Both paths produce a candidate clip package with:

```json
{
  "source_type": "gpt_image_keyframes | comfyui_flf2v",
  "character_id": "<safe-id>",
  "motion_id": "<safe-id>",
  "transition_frame_id": "S0",
  "transition_frame_sha256": "<sha256>",
  "fps": 12,
  "frame_count": 37,
  "canvas": {"width": 0, "height": 0},
  "frames_dir": "frames/",
  "preview_media": "preview/<optional-file>",
  "source_metadata": "source.json",
  "approval_record": "approvals.json"
}
```

The production renderer consumes the normalized PNG frame sequence. Original
GIF, Animated WebP, WebM, or MP4 output may be retained in the ignored
candidate workspace for review, but is not the default precise-transition
runtime source. This avoids browser GIF timing and completion ambiguity while
retaining the generated animation for visual comparison.

Normalization must:

1. decode source media at the configured fixed FPS and canvas;
2. preserve alpha when present or apply the approved matte pipeline;
3. replace decoded frame zero and the final frame with the exact approved S0
   bytes rather than visually similar regenerated copies;
4. validate the second and penultimate frames against S0 to reject or repair a
   visible boundary jump;
5. emit the same manifest fields used by the current `ClipScheduler`;
6. require human identity and motion approval before publication.

## Package layout

```text
AI_Avatar/assets/skills/
└── generate-character-motion/
    ├── SKILL.md
    ├── agents/
    │   └── openai.yaml
    ├── scripts/
    │   ├── init_motion_job.py
    │   ├── render_pose_maps.py
    │   └── validate_motion_job.py
    ├── references/
    │   ├── prompt-contract.md
    │   └── review-gates.md
    └── assets/
        ├── rig.schema.json
        ├── motion.schema.json
        └── scratch-head.motion.json
```

Character-owned reviewed artifacts:

```text
AI_Avatar/assets/
├── reference/
│   └── <character>.png
├── gpt_image_assets/
│   ├── rigs/
│   │   └── <character>.rig.json
│   └── pose-maps/
│       └── <character>/<motion>/*.png
└── comfyui_assets/
    ├── workflows/
    │   └── <reviewed-flf2v-workflow>.json
    ├── motion-presets/
    │   └── <motion>.json
    └── schemas/
        └── comfyui-motion.schema.json
```

Ignored job workspace:

```text
AI_Avatar/.candidates/
├── gpt_image/
│   └── <character>/<motion>/<job-id>/
│       ├── job.json
│       ├── prompts.jsonl
│       ├── opaque/
│       ├── rgba/
│       ├── frames/
│       ├── reports/
│       └── approvals.json
└── comfyui/
    └── <character>/<motion>/<job-id>/
        ├── job.json
        ├── source.json
        ├── preview/
        ├── decoded/
        ├── frames/
        ├── reports/
        └── approvals.json
```

The skill prepares reviewed assets. The existing Avatar publication pipeline
remains the only route into `AI_Avatar/public/`.

Reviewed ComfyUI workflow JSON and motion-preset metadata may be committed only
after absolute paths, credentials, machine-specific queue data, and private
outputs are removed. ComfyUI model weights, generated media, decoded frames,
logs, and API history must never enter Git.

## ComfyUI provider boundary

The avatar project does not import ComfyUI nodes into the runtime and does not
make `/ai_avatar` depend on a live ComfyUI server. A `comfyui_flf2v` provider
adapter owns submission, polling, result retrieval, and bounded cancellation.

Its request contains:

1. a reviewed and sanitized workflow identifier plus workflow hash;
2. the exact approved S0 input for both first and last frame;
3. a bounded motion prompt and optional negative prompt;
4. width, height, FPS, duration, seed, and sampler settings;
5. expected output node and supported media type;
6. character, motion, and job IDs that already passed safe-path validation.

Its result contains only the source media path, reproducibility metadata,
workflow hash, seed, and bounded provider diagnostics. The adapter has no
publication authority and must not leak ComfyUI credentials, absolute
machine paths, full queue history, or raw server responses into reports.

The first implementation reserves this provider contract and committed folder
structure. Downloading large FLF2V model weights or starting a ComfyUI server
is a separate opt-in operation because hardware, storage, and workflow choice
vary by deployment.

## Provider contract

Each flesh-keyframe request contains:

1. the canonical full-body character reference;
2. the current deterministic skeleton pose PNG;
3. the nearest approved flesh keyframe;
4. an identity invariant list;
5. one flat chroma background specification;
6. the exact canvas, framing, and ground-anchor constraints.

An exact `gpt-image-2` API execution requires a locally configured
`OPENAI_API_KEY`. The key is never written to a job, report, prompt log, or Git.
An interactive built-in image-generation tool may be used when available, but
the job metadata must record the execution path and must not claim an exact
model slug when the tool does not expose one.

The provider returns only an opaque candidate and bounded request metadata.
It has no publication authority.

## Character bootstrap

### Reference preflight

Reject before a paid generation call when:

- the reference is missing or unreadable;
- the character is not visible from head/ear tips through both feet;
- the image contains multiple ambiguous subjects;
- the dimensions are below the configured minimum;
- the character touches a canvas edge needed for motion;
- the proposed character ID or output path is unsafe.

### Rig

A vision-capable Agent proposes normalized joint coordinates. A human reviews
and corrects them once. `rig.json` then becomes the stable source of:

- joint IDs and normalized coordinates;
- bone topology;
- left/right semantics from the character's perspective;
- locked joints and movable joints;
- optional anatomy such as long ears, tails, wings, or extra limbs;
- identity regions such as glasses, badge, shirt, tie, and trousers;
- canvas, scale, center, baseline, and ground anchors.

Pose-map rendering is deterministic. GPT Image must never redraw or reinterpret
the skeleton topology.

### Canonical S0

If no reviewed full-body S0 exists, create one candidate from the original
reference on the configured flat chroma background. Convert it to RGBA and
approve it through all four gates before generating a motion.

Henry's current runtime S0 is waist-up. The proof therefore creates a new
full-body candidate S0 and leaves the current runtime/public manifest unchanged.
A later all-state migration must regenerate every loop before this new S0 can
become the shared runtime boundary.

## Scratch-head choreography

The proof is 3 seconds at 12 FPS and yields 37 runtime frame positions,
numbered 0 through 36.

| Runtime frame | Pose |
| ---: | --- |
| 0 | exact full-body S0 |
| 4 | anticipation |
| 8 | character-right paw lift, about 30 degrees |
| 12 | paw lift, about 60 degrees |
| 16 | paw contacts head |
| 20 | scratch offset A |
| 24 | scratch offset B |
| 28 | release |
| 32 | settle |
| 36 | the exact same S0 file and hash as frame 0 |

Locked geometry:

- both feet and the ground baseline;
- hip center and character scale;
- glasses, eyes, badge, shirt, tie, and trousers;
- ear roots.

Allowed motion:

- character-right shoulder, elbow, wrist, and paw;
- a bounded head tilt while the paw contacts the head;
- bounded secondary ear-tip lag;
- breathing-scale motion only after the flesh keyframes are approved.

Intermediate frames are produced only after all sparse flesh keyframes pass
review. The existing FILM/RIFE router may interpolate approved neighboring
keyframes, but it must not invent a missing semantic pose.

## Stage-gated generation

For each keyframe:

1. render the pose PNG from the approved rig and motion definition;
2. assemble the canonical identity, pose, nearest-approved-neighbor, chroma,
   framing, and invariant prompt packet;
3. generate one opaque candidate;
4. convert the candidate to RGBA with a soft matte and despill;
5. run geometry, alpha, and temporal checks;
6. render a contact sheet with the canonical reference, S0, pose map, previous
   approved frame, opaque candidate, and RGBA candidate;
7. require an explicit human approve/reject decision;
8. bind approval to all current input hashes;
9. unlock the next pose only after approval.

Rejecting a candidate permits changing one prompt, pose, or matte variable and
retrying the current stage. A rejected candidate never becomes an input to a
later frame.

## Quality gates

### Geometry

- exact canvas dimensions;
- stable full-body scale, center, feet, and baseline;
- observed joint annotations recorded for review;
- bounded target-joint deviation;
- no detached or duplicated body parts.

Non-human landmark detection is not assumed to be reliable. Observed joints may
come from a reviewed vision inference or manual annotation, but they must be
stored as structured coordinates before approval.

### Alpha

- transparent corners;
- no configured chroma color in opaque subject pixels;
- plausible foreground coverage;
- retained ear and paw tips;
- bounded silhouette area and edge growth relative to neighbors;
- no visible halo or key-color spill.

### Temporal

- bounded center, scale, baseline, and silhouette drift;
- no abrupt identity-region size changes;
- approved adjacent keyframes stay within the configured motion threshold;
- first and final frame IDs and SHA-256 values are identical S0.

### Human identity

The reviewer confirms:

- face, eyes, glasses, fur, and proportions still match the canonical reference;
- the character has the correct number of ears, paws, and legs;
- clothing, tie, badge, and other identity regions are intact;
- the intended paw and head action are semantically correct;
- style, lighting, and material have not drifted.

No automatic metric may replace this decision.

## Approval and resume integrity

An approval record binds:

```json
{
  "pose_id": "scratch-contact",
  "candidate_sha256": "<sha256>",
  "reference_sha256": "<sha256>",
  "rig_sha256": "<sha256>",
  "motion_sha256": "<sha256>",
  "prompt_sha256": "<sha256>",
  "automatic_gates": "passed",
  "human_decision": "approved"
}
```

Resume may reuse an approved frame only when every bound hash still matches.
Changing the reference, rig, motion, prompt, or candidate invalidates that
stage and all downstream anchored-neighbor stages.

## Error handling

- Invalid reference, rig, motion, or path: fail before any paid request.
- `429` or `5xx`: bounded retry with backoff and request ID.
- Authentication/quota failure: stop with a safe operator hint.
- Moderation or other user-correctable image error: do not retry unchanged;
  require prompt or input revision.
- Automatic gate failure: preserve the candidate in the ignored workspace and
  retry only the current pose after one targeted change.
- Human rejection: record the decision without embedding private reviewer data.
- Interrupted job: resume only from hash-valid approvals.

Logs and reports must exclude credentials and raw provider response bodies.
Generated images and prompt packets remain ignored candidates until approved.

## Testing

### Skill TDD

Before authoring `SKILL.md`, run a baseline scenario without the skill and
capture where an Agent:

- treats a skeleton picture as ControlNet;
- generates all frames before review;
- recursively propagates a rejected neighbor;
- publishes candidates directly;
- logs credentials or assumes transparent GPT Image 2 output.

After authoring, forward-test the same request with the skill and confirm the
Agent follows the staged workflow and capability boundaries.

### Offline default suite

- strict rig and motion schema validation;
- unsafe ID and path rejection;
- deterministic pose-map rendering;
- non-human extension-joint support;
- prompt packet contains all required references and invariants;
- chroma matte and alpha edge validation from golden fixtures;
- approval hash invalidation and downstream invalidation;
- job resume from the nearest still-valid approved stage;
- no next-stage generation before human approval;
- exact shared S0 at both boundaries;
- reports and logs contain no API key or raw provider response;
- publication is impossible from the candidate runner.
- both provider paths validate against the same candidate clip schema;
- ComfyUI workflow sanitization rejects credentials, absolute paths, and
  unsupported output nodes;
- ComfyUI normalization uses the exact S0 bytes at both boundaries;
- fixed-FPS decode is deterministic from golden source media;
- second-to-S0 and penultimate-to-S0 temporal gates reject visible loop jumps;
- source preview media cannot be published directly by the candidate runner.

### Integration and live acceptance

Golden-image integration tests exercise the complete offline candidate,
matting, reporting, and contact-sheet flow without network access.

One opt-in live acceptance generates a single GPT Image 2 candidate. It is
charged, never runs in default CI, and cannot auto-approve or publish. The
Henry proof loop proceeds one live keyframe at a time under the same review
contract.

## Success criteria

- The skill passes structural validation and forward-testing.
- A new full-body Henry rig and deterministic scratch-head skeleton timeline
  are reviewed.
- One full-body scratch-head proof loop passes all automatic and human gates.
- Its first and final frames reference the same exact candidate S0.
- `gpt_image_assets` and `comfyui_assets` remain interchangeable candidate
  sources behind one normalized clip and publication contract.
- The ComfyUI path can retain generated GIF/video previews while producing a
  deterministic frame sequence that the existing scheduler can switch only at
  the shared S0 boundary.
- Existing six runtime loops and `/ai_avatar` remain unchanged in this phase.
- No credentials, private job cache, rejected candidates, or provider traces
  enter Git.

## Out of scope

- Downloading or integrating ControlNet weights.
- Claiming that GPT Image pose references are hard latent constraints.
- Automatically replacing all six current runtime loops.
- Automatically approving identity or semantic anatomy.
- Publishing a new shared runtime S0 before every state is migrated.
- Downloading ComfyUI FLF2V model weights or requiring ComfyUI at runtime.
- Treating the presence of identical first/last conditioning images as proof
  of a seamless generated loop without temporal validation.
- Using native GIF completion events as the precise state-transition clock.
