# AI Avatar verification

Hardware-free asset and manifest tests:

```bash
python -m pytest tests/avatar -q
```

Browser runtime tests:

```bash
cd frontend/realtime
npm test -- --run src/avatarLab
npm run build:avatar
```

Gateway/Docker delivery:

```bash
python -m pytest tests/test_webui.py tests/test_docker_runtime.py -q
```

The suite covers inventory bounds, GrabCut regression points, normalization,
FILM/RIFE routing, resumable pair hashes, quality gates, report-hash approval,
shared `S0`, preload readiness, latest-selection scheduling, fixed Canvas
rendering, `/ai_avatar`, and absence of browser audio activation.

Static tests do not prove visual motion. Before release, watch all six loops at
normal FPS and click several states within one active loop. Confirm only the
last click is queued, the old loop reaches `S0`, and the new loop starts without
a viewport or anchor jump. This review must not grant microphone permission or
play audio.
