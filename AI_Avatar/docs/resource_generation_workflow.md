# Resource Generation Workflow

## Source sheets

The visual sheets are in `assets/sheets/`.

## Extraction output

Crop each animation row into:

```text
assets/generated_frames/<clip_id>/frame_001.png
assets/generated_frames/<clip_id>/frame_002.png
...
```

Optional exports:

```text
assets/generated_gif/<clip_id>.gif
assets/generated_gif/<clip_id>.webp
```

## Quality rules

- fixed output canvas
- consistent character scale
- consistent bottom anchor
- no frame-to-frame crop drift
- first and final frames close to anchor where applicable
- use alpha background after cropping if practical

## Recommended command flow

```bash
python AI_Avatar/scripts/extract_frames.py   --manifest AI_Avatar/config/animation_manifest.json

python AI_Avatar/scripts/build_animations.py   --manifest AI_Avatar/config/animation_manifest.json   --format webp
```
