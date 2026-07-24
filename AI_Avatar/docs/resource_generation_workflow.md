# AI Avatar Resource Generation Workflow

Asset generation is offline and review-gated. Gateway or WebUI startup must
never download a provider or generate frames.

The current six published loops are sheet-derived and use FILM/RIFE for
interpolation. New semantic motions follow the approved
[ComfyUI FLF2V-first architecture](../../spec/references/20260724-comfyui-avatar-motion-design.md).
There is no GPT Image fallback.

## 1. Verified source inventory

`config/verified_asset_inventory.json` records visually checked crop boxes.
Do not infer content from filenames: the six MVP states span sheets `01`,
`03`, and `04`, and full-body cells are intentionally normalized to a common
waist-up composition.

Run:

```bash
python AI_Avatar/tools/build_avatar_assets.py inspect \
  --output runtime/avatar-review/contact-sheet.png
```

The contact sheet must show no card number, row label, border, or scale drift.

## 2. Segmentation and normalization

Near-white clothing touches near-white sheet backgrounds, so threshold-only
edge flood fill is unsafe. Production extraction uses OpenCV GrabCut with:

- definite background only at the crop border;
- probable foreground across the inner crop;
- dark or chromatic pixels as strong foreground seeds;
- largest connected component cleanup after segmentation.

Each result is rendered to a transparent 512 × 512 canvas with a fixed
height/width cap and bottom anchor `(0.5, 0.92)`. Regression checks must keep
the white shirt, both sleeves, hands, and trousers while removing sheet UI.

```bash
python AI_Avatar/tools/build_avatar_assets.py extract
```

## 3. Current FILM and RIFE post-processing

Provider repositories are pinned by commit in
`config/interpolation_providers.json`. Official weights live below ignored
`models/avatar_interpolation/`.

```bash
AI_Avatar/tools/setup_interpolation_models.sh
```

The script is idempotent and works offline when the pinned checkout and weights
already exist. RIFE is the fast path for small silhouette motion; FILM handles
larger motion. The calibrated large-motion threshold is `0.12`.

The official FILM evaluation CLI imports Apache Beam. Agent Speak instead uses
`tools/film_pair_cli.py`, a local pair adapter around the official SavedModel.
It interpolates premultiplied RGB while a signed-distance silhouette morph
preserves alpha. RIFE v3.6 directly preserves RGBA for the reviewed small-motion
pairs.

Frame interpolation cannot invent a reliable missing pose between unrelated
images. If a hand jumps from 0° to 90° without valid source structure, add
reviewed keyframes or keep the clip in `needs_keyframe`; do not approve a
deformed result.

For new continuous actions, generate semantic motion with a reviewed ComfyUI
FLF2V workflow using the same S0 at both boundaries. Use FILM/RIFE afterward
only for fixed-FPS resampling or a short, already-correct transition.

## 4. Interpolate every segment

Interpolation covers:

- shared `S0` → first core keyframe;
- every adjacent core keyframe pair;
- final core keyframe → shared `S0`.

Skipping core keyframe pairs leaves visible jitter even when entry/exit is
smooth. Each transition writes `transition.json` with input hashes, provider,
and exponent. Matching work is reused after interruption; changed inputs are
regenerated.

```bash
python AI_Avatar/tools/build_avatar_assets.py review --provider auto
```

## 5. Quality and human review

Reports measure duplicate ratio, adjacent delta, alpha growth, baseline drift,
and center drift. Metrics are a gate, not proof of visual quality. Inspect each
loop for ears, paws, glasses, clothing, facial detail, transparency, scale, and
the identical first/final `S0`.

Generated clean candidates remain `needs_review`. Fatal metrics become
`needs_keyframe`. Only a current report SHA can approve a clip.

## 6. Publish and rebuild

Publish all six approved hashes, run `validate`, then:

```bash
cd frontend/realtime
npm run build:avatar
```

Only `AI_Avatar/public/` and `web/ai_avatar/` are product artifacts. Never
commit `.providers/`, `.candidates/`, model weights, or runtime review files.
