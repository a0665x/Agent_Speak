# Scripts

The local agent should implement:

- `extract_frames.py`: crop rows/cells from source sheets using manifest crop metadata
- `build_animations.py`: export PNG sequences to GIF or Animated WebP
- `validate_assets.py`: verify expected clips and frame counts

The current package provides the architecture and source sheets; crop coordinates may need one manual calibration pass per sheet.
