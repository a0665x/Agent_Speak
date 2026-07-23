# Testing

Docker-first regression is `./run.sh --test`. It starts a one-shot container from the production image with model bootstrap disabled, runs the complete pytest suite, syntax-checks `web/app.js`, `web/codex-recorder-core.js`, and `web/codex.js`, executes `tests/codex_recorder_core.test.js`, prints `TESTS_OK`, and removes the test container. `tests/test_model_bootstrap.py` covers fixed revisions, allow-listed artifacts, disk reserve, cache adoption, exact validation, and scoped partial cleanup. `tests/test_docker_runtime.py` guards the downloader/runtime target split, verify-only startup, `/dev/snd`, persistent mounts, and root lifecycle dispatch. Release verification must additionally execute `--models` once, verify its cached no-op, then exercise `--build`, `--up`, `--status`, `--logs`, `--down`, `--down_up`, `--restart`, `--test`, and `--rebuild` against the real Docker daemon.

Structured diagnostic regressions verify JSON Lines formatting, stable one-way session references, payload allowlisting, bounded rotation, HTTP correlation IDs, ASR provider exception typing, and realtime retry records. Tests must assert that raw session IDs, audio, transcript text, credentials, request bodies, provider messages, and private paths never appear. `tests/test_docker_runtime.py` also guards the per-service `--logs` allowlist and persistent but independently owned Gateway/ASR runtime mounts.

The regression container is intentionally CPU-only even on an NVIDIA host. GPU acceptance is a separate host integration check:

```bash
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --build
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --rebuild
./run.sh --status
docker compose -f compose.yaml -f compose.gpu.yaml exec -T gateway nvidia-smi -L
```

Forced CPU must report `accelerator=cpu asr_device=cpu`. Automatic NVIDIA selection requires a working driver and NVIDIA Container Toolkit, must report `accelerator=nvidia asr_device=cuda`, and must expose the GPU inside the Gateway. A GPU mapping alone is insufficient: a bounded real ASR request must also complete without CUDA library errors.

Resource orchestration regressions cover pure policy planning, atomic state replacement, Unix-socket framing and permissions, serialized fixed Compose actions, bounded Gateway errors, four-language OpenAPI metadata, dynamic ASR/TTS readiness, and both UI reset controls. Hardware acceptance must additionally record the Gateway container ID, reconcile/reset ASR and TTS, poll each operation to a terminal phase, and prove the Gateway ID did not change. `exclusive` must restore the prior ready profile after a target reset; `concurrent`/`multi_gpu` must leave the other workload running. No smoke may request microphone permission, capture audio, synthesize, or play unless that action has separate explicit user consent.

The missing-supervisor regression must cover the actual daemon-launch argv,
including its required `server` subcommand; a fake successful `client ping`
cannot prove that path. High-VRAM acceptance must also record the NVIDIA
reported capacity, configured 18,500 MB default concurrent threshold, resolved
policy, peak unified-memory use, both worker health states, and before/after
Gateway IDs. See
[Resource Orchestrator Runtime and Reset Troubleshooting](references/lesson-20260723-resource-orchestrator-troubleshooting.md).

OpenAPI docs regression: `/docs` depends on Swagger UI assets from jsDelivr and FastAPI's inline initializer. The security middleware must apply the docs-specific CSP only to `/docs` and `/redoc`, while `/` retains the stricter self-only WebUI CSP. `test_openapi_docs_csp_allows_swagger_assets_without_weakening_webui` guards both sides of this contract. Runtime verification must confirm `/openapi.json` returns JSON and the real `/docs` browser renders `.swagger-ui` without a visible fetch error.


`./scripts/test.sh` runs pytest plus JavaScript syntax checking for contracts, typed provider boundaries, event ordering and WebSocket replay, pipeline completion/failure, separate stage failures, WAV bounds, VAD, speaker persistence/matching, routes, operations, and UI delivery.

`./scripts/health_smoke.sh`, `./scripts/smoke_api.sh`, and `./scripts/tailscale_https.sh` automatically prefer a running Docker Compose `gateway`, execute Python validation inside the production container, and therefore work in a fresh Release install without a host `.venv`. If the Compose Gateway is not running, the scripts fall back to the project `.venv`. The health smoke validates `status=ok` and writable storage; the API smoke exercises health, session creation, synthetic voiced turn, ordered WebSocket events, WAV artifact, and speaker create/enroll/match/delete lifecycle. Expected markers include `HEALTH_SMOKE_OK mode=docker|local`, `API_SMOKE_OK mode=docker|local`, and `TAILSCALE_HTTPS_SMOKE_OK mode=docker|local`.

`./scripts/mic_smoke.sh` uses USB ALSA capture and reports peak/RMS/nonzero ratios.

`tests/test_mcp_server.py` 是 MCP control-plane 的硬體隔離回歸測試。它注入 fake HTTP client 與 subprocess runner，因此 CI 不需要真實 microphone、speaker、gateway 或 model；覆蓋 status/capabilities、command timeout、缺少 ALSA utilities、有效 PCM WAV 驗證、暫存清理、不安全 device 拒絕、逐次使用者同意、ASR HTTP delegation，以及 synthesized 與 physically played 的區別。`tests/test_mcp_stdio.py` 會實際啟動 `scripts/run_mcp.sh`、完成 MCP initialize/list_tools，並確認敏感工具公開 `user_confirmed` schema。可重現 focused command：`.venv/bin/pytest -q tests/test_mcp_server.py tests/test_mcp_stdio.py`。實體 hardware smoke 仍是獨立驗收，不可從 mocked tests 推論。

Production speech regression is covered by `tests/test_production_providers.py`: Faster-Whisper must consume the WAV and return segment text, Piper must return a non-empty spoken PCM WAV, and the default provider set must advertise ASR/TTS as non-development providers. The same suite executes `setup.sh` from outside the repository to prove `.env` is loaded before relative model resolution, and verifies that ASR capability `ready` is false when the configured model is not locally usable and becomes true when its required cached files are present. Runtime verification must additionally synthesize a Chinese phrase with the real Piper model, feed that WAV to the real Faster-Whisper model, and complete a live full-turn request; a RIFF file or HTTP 200 alone does not prove that the old tone/hash stubs are gone.

`./scripts/tailscale_https.sh smoke` verifies the real tailnet HTTPS certificate, `/api/v1/health`, and the root WebUI through the configured Tailscale Serve URL without bypassing TLS validation. Its regression tests prove both runtime branches: a running Compose Gateway works without host `.venv`, while an absent Gateway uses the local `.venv` fallback. Before handing over a phone URL, also confirm `tailscale serve status` maps the exact HTTPS port to `http://127.0.0.1:${AGENT_SPEAK_PORT:-8765}`.

UI work requires desktop/mobile viewport checks, console-error inspection, visible interaction feedback, API state, and horizontal-overflow verification. `tests/test_webui.py::test_capture_toggle_targets_the_explicit_upload_label` protects initialization by requiring the upload label to have an explicit DOM id used by `setCaptureDisabled`; the file input and label are sibling elements, so ancestor lookup such as `input.closest("label")` is invalid.

README screenshot and animated-tour capture is a read-only browser verification workflow: it must use English presentation, must not request microphone permission, must not click device-check or listening controls, and must not synthesize or play audio. Captured PNGs and the GIF may show idle device, pipeline, transcript, graph, and API-documentation states only.

Codex CLI recorder regression uses `tests/test_webui.py` for `/codex` delivery and browser-integration hooks, plus `node tests/codex_recorder_core.test.js` for system-default device selection, fallback behavior, button-state rules, and timer formatting. Real-headset acceptance is separate: the operator grants browser microphone permission, verifies the displayed current input and output labels, explicitly starts and stops one bounded recording, checks raw and corrected text, and pastes the copied result into Codex CLI. Browser enumeration is not evidence of physical playback, and this workflow performs no playback test.

Localization regressions require English as the first paint and complete `en`, `zh-TW`, `ja`, and `ko` presentation catalogs across the project guide, ASR Realtime, and Swagger. Tests cover query-over-storage precedence, invalid-locale fallback, route propagation, localized endpoint and field metadata, and preservation of completed transcript/response nodes across language changes. Runtime browser smoke must switch languages, reload to prove persistence, then process a real WAV and switch again to prove result text is unchanged.

Realtime speech-language regressions additionally cover the five public policies (`auto`, `en`, `zh-TW`, `ja`, `ko`), the compatible `zh-TW` default, immutable session/event serialization, propagation through realtime queues, `zh-TW → zh` and `auto → None` Whisper mappings, reuse of one loaded ASR model, language-specific endpoint/correction prompts and fallbacks, and next-session-only UI changes while listening. The durable contract and the 2026-07-21 verification baseline are recorded in [`references/lesson-20260721-session-language-routing.md`](references/lesson-20260721-session-language-routing.md).

OpenAPI usability tests require all four localized API descriptions, every tag group, endpoint input/output descriptions, parameter and response-field descriptions, text examples, and WAV request constraints while proving identical structural identifiers. Remote `/docs?lang=en` verification must still prove rendered Swagger operations, zero browser errors, and a valid non-empty `/openapi.json?lang=en`.

When a sandbox prohibits all socket binding, ASGI HTTP/WebSocket integration remains executable but live Uvicorn, API smoke, and browser-daemon checks must be rerun on an unrestricted host; they must not be reported as passing from static checks alone.

## VoxCPM2 clone acceptance

Hardware-free tests cover pinned model files, byte/duration bounds, 20 ms reference assessment, allowlisted style cues, worker request/error normalization, direct-WAV API privacy, four-language Swagger, Compose isolation, GPU-mode switching, transient Blob cleanup, explicit Generate/Play separation, device gating, Orb semantics, reduced motion, and responsive routes.

The GPU smoke uses a deterministic synthetic PCM WAV and validates a 48 kHz response without calling `getUserMedia`, `arecord`, `aplay`, or a physical speaker. Real-device acceptance is separate and requires the user to click **Check devices**, **Start recording**, **Stop & check**, and **Play**. Test screenshots must not grant microphone permission or start playback. After GPU smoke, restore ASR with `./run.sh --asr-up`.

Turing runtime acceptance additionally requires a real cold start to `ready`,
one default-voice synthesis, one synthetic-reference clone synthesis, and
48 kHz mono PCM validation for both outputs. Static regressions guard the
256 MiB KV limit, executable Triton cache location, pinned VoxCPM dependency,
fail-closed FP16 adapter patch, and suppression of upstream request/access INFO
logs that would otherwise reveal synthesis text.
