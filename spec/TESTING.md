# Testing

`./scripts/test.sh` runs pytest for contracts, event ordering, pipeline completion/failure, WAV bounds, VAD, speaker persistence/matching, routes, and UI delivery.

`./scripts/smoke_api.sh` exercises health, session creation, synthetic voiced turn, events and speaker lifecycle. `./scripts/mic_smoke.sh` uses USB ALSA capture and reports peak/RMS/nonzero ratios.

UI work requires desktop/mobile viewport checks, console-error inspection, visible interaction feedback, API state, and horizontal-overflow verification.
