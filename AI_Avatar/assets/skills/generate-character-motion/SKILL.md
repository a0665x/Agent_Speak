---
name: generate-character-motion
description: Use when creating, reviewing, interpolating, or publishing continuous character animation from a full-body reference, skeleton pose maps, GPT Image candidates, or ComfyUI first-last-frame video.
---

# Generate Character Motion

## Core principle

Treat every generated image or video as an ignored candidate. A pose image is
not ControlNet unless the selected provider exposes real ControlNet
conditioning. Automatic checks never replace human approval, and candidate
tools have no publication authority.

## Choose a source

| Need | Source |
| --- | --- |
| Exact reviewed semantic poses | `gpt_image_assets` |
| Natural short motion between identical boundaries | `comfyui_assets` |

Both sources must finish as a validated PNG sequence with the exact shared S0
bytes and hash at the first and final frame.

## Required workflow

1. Preflight one full-body `assets/reference/*.png`.
2. Create or load a reviewed rig and canonical full-body S0.
3. Render pose maps deterministically.
4. Initialize a job below `AI_Avatar/.candidates/`.
5. Generate only the currently unlocked one keyframe.
6. Apply matte, anatomy, geometry, temporal, and identity-region gates.
7. Show the contact sheet and wait for explicit human approval.
8. Bind approval to candidate, reference, S0, rig, motion, and prompt hashes.
9. Unlock only the next keyframe. Rejection never becomes a neighbor.
10. Interpolate only between approved semantic poses.
11. Validate the shared S0 boundaries and neighboring frames.
12. Hand the candidate package to the existing reviewed publisher separately.

Read [prompt-contract.md](references/prompt-contract.md) before a provider call
and [review-gates.md](references/review-gates.md) before accepting a decision.

## Non-negotiable boundaries

- Say “visual skeleton pose instruction, not ControlNet” for GPT Image.
- Never generate all keyframes before stage review.
- Clean automatic gates mean `needs_review`, never approved.
- Never auto-publish, even when the user authorized generation.
- Keep opaque output, RGBA frames, previews, prompts, reports, and decisions in
  the ignored candidate workspace until reviewed.
- You must never log credentials, authorization headers, signed URLs, or raw provider
  responses.
- Never commit model weights, generated media, rejected candidates, logs, or
  private reviewer data.
- An approval is stale when any bound input hash changes.

## Red flags

- “It looks clean, so human review is unnecessary.”
- “The user approved the project, so publication is implied.”
- “A skeleton image plays the same role, so call it ControlNet.”
- “Generate the full batch now and review later.”
- “Include the key or raw response for reproducibility.”

Stop at the current stage when any red flag appears. Record only sanitized
provider metadata and request a decision without unlocking downstream work.
