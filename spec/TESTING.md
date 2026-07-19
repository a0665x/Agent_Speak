# Testing

OpenAPI docs regression: `/docs` depends on Swagger UI assets from jsDelivr and FastAPI's inline initializer. The security middleware must apply the docs-specific CSP only to `/docs` and `/redoc`, while `/` retains the stricter self-only WebUI CSP. `test_openapi_docs_csp_allows_swagger_assets_without_weakening_webui` guards both sides of this contract. Runtime verification must confirm `/openapi.json` returns JSON and the real `/docs` browser renders `.swagger-ui` without a visible fetch error.


`./scripts/test.sh` runs pytest plus JavaScript syntax checking for contracts, typed provider boundaries, event ordering and WebSocket replay, pipeline completion/failure, separate stage failures, WAV bounds, VAD, speaker persistence/matching, routes, operations, and UI delivery.

`./scripts/smoke_api.sh` exercises health, session creation, synthetic voiced turn, events and speaker lifecycle. `./scripts/mic_smoke.sh` uses USB ALSA capture and reports peak/RMS/nonzero ratios.

`./scripts/tailscale_https.sh smoke` verifies the real tailnet HTTPS certificate, `/api/v1/health`, and the root WebUI through the configured Tailscale Serve URL without bypassing TLS validation. Before handing over a phone URL, also confirm `tailscale serve status` maps the exact HTTPS port to `http://127.0.0.1:${AGENT_SPEAK_PORT:-8765}`.

UI work requires desktop/mobile viewport checks, console-error inspection, visible interaction feedback, API state, and horizontal-overflow verification. `tests/test_webui.py::test_capture_toggle_targets_the_explicit_upload_label` protects initialization by requiring the upload label to have an explicit DOM id used by `setCaptureDisabled`; the file input and label are sibling elements, so ancestor lookup such as `input.closest("label")` is invalid.

Localization regressions are protected by tests requiring a Traditional Chinese first paint, the persistent English switch, beginner workflow guidance, and preservation of completed transcript/response nodes across language changes. Runtime browser smoke must switch languages, reload to prove persistence, then process a real WAV and switch again to prove result text is unchanged.

OpenAPI usability tests require the Chinese API description, six tag groups, endpoint input/output descriptions, text examples, and WAV request constraints. Remote `/docs` verification must still prove rendered Swagger operations, zero browser errors, and a valid non-empty `/openapi.json`.

When a sandbox prohibits all socket binding, ASGI HTTP/WebSocket integration remains executable but live Uvicorn, API smoke, and browser-daemon checks must be rerun on an unrestricted host; they must not be reported as passing from static checks alone.
