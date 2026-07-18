# Testing

`./scripts/test.sh` runs pytest plus JavaScript syntax checking for contracts, typed provider boundaries, event ordering and WebSocket replay, pipeline completion/failure, separate stage failures, WAV bounds, VAD, speaker persistence/matching, routes, operations, and UI delivery.

`./scripts/smoke_api.sh` exercises health, session creation, synthetic voiced turn, events and speaker lifecycle. `./scripts/mic_smoke.sh` uses USB ALSA capture and reports peak/RMS/nonzero ratios.

UI work requires desktop/mobile viewport checks, console-error inspection, visible interaction feedback, API state, and horizontal-overflow verification. `tests/test_webui.py::test_capture_toggle_targets_the_explicit_upload_label` protects initialization by requiring the upload label to have an explicit DOM id used by `setCaptureDisabled`; the file input and label are sibling elements, so ancestor lookup such as `input.closest("label")` is invalid.

When a sandbox prohibits all socket binding, ASGI HTTP/WebSocket integration remains executable but live Uvicorn, API smoke, and browser-daemon checks must be rerun on an unrestricted host; they must not be reported as passing from static checks alone.
