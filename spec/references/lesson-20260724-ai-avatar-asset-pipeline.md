# Lesson: AI Avatar asset extraction and continuous-loop generation

## Summary

Henry source art was complete, but threshold segmentation removed white
clothing and the initial interpolation pipeline smoothed only state boundaries.
GrabCut segmentation, adjacent-core interpolation, provider-specific RGBA
handling, and resumable hash caches produced six reviewed shared-S0 loops.

## Context

- Project: Agent Speak
- Date: 2026-07-24
- Area: `AI_Avatar` offline assets and `/ai_avatar`
- Trigger: build continuous state loops from the supplied Henry sheets
- Related request: one shared first/final frame and boundary-only state changes

## Symptoms

- Early contact sheets showed transparent holes through Henry's white shirt,
  sleeve, trousers, and raised hand.
- FILM output appeared deformed even though the original sheet looked complete.
- Listening and Thinking still jumped inside a loop after entry/exit
  interpolation.
- Long all-state review commands could be terminated before completion.
- FILM's official local CLI failed with
  `ModuleNotFoundError: No module named 'apache_beam'`.
- Docker test collection failed because the host happened to provide SciPy but
  the `test` extra did not.
- `./run.sh --test` reused an old `frontend-test` image and initially reported
  19 files / 86 tests instead of the current 25 files / 120 tests.

## Expected Behavior

All six loops should retain the complete character, keep one 512 × 512
viewport/anchor, interpolate every visible motion segment, and begin/end on the
same `henry_s0`. A restarted offline build should reuse only still-valid work.

## Evidence

- `04_gesture_keyframes.png` visibly contained complete sleeves and trousers.
- Edge-threshold extraction classified the near-white shirt as connected
  background; normalized endpoints were already damaged before interpolation.
- GrabCut probe retained the right sleeve at source coordinate `(110, 150)` and
  trousers at `(72, 184)` while removing the top background.
- Before core interpolation, max adjacent delta was `0.214` for Listening and
  `0.222` for Thinking; afterward it was `0.072` and `0.088`.
- Final reports contained no failed rules and baseline drift was at most
  `0.00390625` of the 512 px viewport.
- `python AI_Avatar/tools/build_avatar_assets.py validate` reported
  `AVATAR_ASSETS_VALID clips=6 transition=henry_s0`.

## Hypotheses considered

1. FILM generated the transparent clothing holes.
   - Evidence for: holes were obvious in interpolated frames.
   - Evidence against: the same holes existed in extracted endpoints.
   - Result: rejected; segmentation was the upstream cause.
2. Interpolating alpha through FILM would repair transparency.
   - Evidence against: mask inference created internal holes; chroma-key
     compositing created green spill and canvas-edge artifacts.
   - Result: rejected.
3. Entry/exit interpolation alone made each state continuous.
   - Evidence against: source core poses still had large adjacent deltas.
   - Result: rejected; every adjacent core keyframe pair also needs routing.
4. Frame interpolation can synthesize any 0°→90° pose.
   - Evidence against: unrelated structures smear or disappear when endpoints
     do not contain a plausible motion path.
   - Result: add keyframes or mark `needs_keyframe`; never approve deformation.

## Root cause

`remove_border_background()` treated near-white foreground as border-connected
background. `retain_largest_component()` could not reconstruct the removed
pixels. Separately, `assemble_candidate_loop()` inserted frames only before and
after the whole core sequence, leaving core keyframes discontinuous. The
official FILM evaluation entry also carried an unnecessary Apache Beam runtime
for a local two-frame job.

## Fix

- `images.segment_character()` now initializes deterministic OpenCV GrabCut
  from crop borders, inner probable foreground, and strong color seeds.
- `assemble_candidate_loop()` routes entry, every core pair, and exit.
- RIFE v3.6 handles reviewed small-motion RGBA pairs.
- `film_pair_cli.py` calls the official FILM SavedModel without Beam, uses
  premultiplied RGB, and derives continuous alpha from signed-distance masks.
- Each generated pair records provider, exponent, and endpoint SHA-256 in
  `transition.json`; matching work resumes after interruption.
- Publishing requires exact current report hashes and copies only six approved
  clips.
- The `test` extra now declares SciPy because Avatar tests import the local FILM
  adapter.
- `./run.sh --test` builds `gateway-test` and `frontend-test` before execution,
  so a stale image cannot hide newly added tests.

## Verification

- [x] `python -m pytest tests/avatar -q` — 48 passed at asset publication
- [x] `npm test` — 25 files / 120 tests passed after WebUI integration
- [x] `python -m pytest tests/test_webui.py tests/test_docker_runtime.py -q` —
  54 passed
- [x] `python AI_Avatar/tools/build_avatar_assets.py validate` — six clips,
  shared `henry_s0`
- [x] six-row contact sheet visually reviewed
- [x] live Gateway manifest/asset smoke test and long-lived headless browser DOM
  check (`Assets Ready`, enabled controls, 512 × 512 character Canvas)
- [ ] physical browser interaction after the final Docker rebuild

## Deployment notes

- Generated product artifacts: `AI_Avatar/public/`, `web/ai_avatar/`
- Rebuild required after source/runtime changes: `npm run build:avatar` or
  `./run.sh --build`
- Restart required for a running old Gateway image
- Ignored runtime dependencies: `.providers/`, `.candidates/`,
  `models/avatar_interpolation/`
- The WebUI itself does not require interpolation models.

## Future guardrails

- Inspect extracted endpoints before blaming FILM or RIFE.
- Never use threshold-only segmentation for white clothing on a white sheet.
- Interpolate adjacent core keyframes, not only S0 entry/exit.
- Treat metrics as gates; visually inspect morphology and alpha.
- Do not install Apache Beam for the local FILM pair path.
- Preserve report-hash approval and transition input-hash resume behavior.
- Treat an unexpectedly smaller Docker test count as stale-image evidence;
  rebuild test targets before accepting results.
- Keep tool-only dependencies in both the `avatar` extra and the `test` extra
  when the default suite imports those tools.
- Read `AI_Avatar/README.md`, the Motion Lab design, and this lesson first.
