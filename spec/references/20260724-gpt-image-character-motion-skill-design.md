# GPT Image Character Motion Skill Design

**Date:** 2026-07-24
**Branch:** `feature/ai-avatar-motion-lab`
**Status:** Approved design; implementation not started

## Goal

Add a project-local skill that turns a reviewed full-body character reference
into a reproducible rig, deterministic skeleton pose maps, and staged
GPT Image flesh keyframes. Prove the workflow with one three-second Henry
scratch-head loop without replacing the six existing runtime loops.

The skill must generalize from `AI_Avatar/assets/reference/*.png`; it must not
hard-code Henry's anatomy, identity, or motion into the runner.

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
├── rigs/
│   └── <character>.rig.json
└── pose-maps/
    └── <character>/<motion>/*.png
```

Ignored job workspace:

```text
AI_Avatar/.candidates/generative/
└── <character>/<motion>/<job-id>/
    ├── job.json
    ├── prompts.jsonl
    ├── opaque/
    ├── rgba/
    ├── reports/
    └── approvals.json
```

The skill prepares reviewed assets. The existing Avatar publication pipeline
remains the only route into `AI_Avatar/public/`.

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
- Existing six runtime loops and `/ai_avatar` remain unchanged in this phase.
- No credentials, private job cache, rejected candidates, or provider traces
  enter Git.

## Out of scope

- Downloading or integrating ControlNet weights.
- Claiming that GPT Image pose references are hard latent constraints.
- Automatically replacing all six current runtime loops.
- Automatically approving identity or semantic anatomy.
- Publishing a new shared runtime S0 before every state is migrated.
