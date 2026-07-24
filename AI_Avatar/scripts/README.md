# AI Avatar tooling

The implemented entry point is:

```bash
python AI_Avatar/tools/build_avatar_assets.py --help
```

Phases:

- `inspect`: write a normalized source contact sheet;
- `extract`: write ignored shared/core candidate frames;
- `review --provider auto|film|rife|none`: interpolate, score, and preview;
- `publish --approve CLIP_ID:REPORT_SHA256`: copy only current approved clips;
- `validate`: verify paths, hashes, RGBA dimensions, quality, and shared `S0`.

Provider checkout verification:

```bash
AI_Avatar/tools/setup_interpolation_models.sh
```

Do not restore the obsolete `extract_frames.py`/`build_animations.py` design or
write directly into `public/`. Candidate generation and approval are separate
on purpose.
