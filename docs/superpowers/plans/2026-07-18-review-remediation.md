# Review Remediation Implementation Plan

> **For agentic workers:** Execute inline with strict red-green TDD. Do not commit because the workspace `.git` directory is read-only.

**Goal:** Resolve all Important review findings and the straightforward Minor findings without removing staged features or changing the visual layout.

**Architecture:** Keep synchronous provider protocols, but invoke every provider and synchronous speaker-store operation with `asyncio.to_thread`. Add small focused helpers for streamed request ingestion, bounded PCM-WAV validation, per-session admission, bounded broker retention, and bounded artifact retention. Preserve endpoint detection as informational metadata so full turns always continue through agent and TTS.

**Tech Stack:** Python 3.11, FastAPI/Starlette, Pydantic, NumPy, SQLite, vanilla JavaScript, pytest/httpx.

## Global Constraints

- Target Python 3.11 and aarch64 Jetson AGX Orin.
- Keep provider protocols synchronous and preserve ordered event delivery.
- Keep the current WebUI layout and existing API features.
- Observe every new regression test fail for the intended reason before production changes.
- Do not commit or modify git history.

---

### Task 1: Private storage and safe network defaults

**Files:** `tests/test_speakers.py`, `tests/test_contracts.py`, `tests/test_operations.py`, `src/agent_speak/config.py`, `src/agent_speak/speakers.py`, `.env.example`, `README.md`, `spec/RUNTIME.md`.

- [ ] Add tests asserting 0700 private directories, 0600 database/sample files, loopback defaults, and an explicit LAN warning.
- [ ] Run the focused tests and confirm permission/default assertions fail.
- [ ] Apply explicit chmod/open modes and change the default host/documentation.
- [ ] Re-run focused tests and confirm they pass.

### Task 2: Streaming ingress and security headers

**Files:** `tests/test_stage_api.py`, `tests/test_speakers.py`, `tests/test_app.py`, `src/agent_speak/app.py`.

- [ ] Add ASGI-level tests proving oversized chunked requests stop reading at the configured limit for turn, audio-stage, and speaker binary endpoints, plus header assertions.
- [ ] Run focused tests and confirm materialized body/header behavior fails.
- [ ] Add a streamed bounded-body helper and global CSP, nosniff, and referrer middleware.
- [ ] Re-run focused tests and confirm they pass.

### Task 3: Async provider boundary and turn admission

**Files:** `tests/test_sessions_pipeline.py`, `tests/test_stage_api.py`, `src/agent_speak/pipeline.py`, `src/agent_speak/app.py`, `src/agent_speak/sessions.py`.

- [ ] Add heartbeat tests around blocking providers and a concurrent same-session request test expecting stable `409 turn_in_progress`.
- [ ] Run focused tests and confirm event-loop starvation/concurrent admission failures.
- [ ] Invoke synchronous operations through `asyncio.to_thread`, add per-session non-waiting admission, and keep ordered event emission.
- [ ] Re-run focused tests and confirm they pass.

### Task 4: Failure events, bounded broker lifecycle, and artifacts

**Files:** `tests/test_sessions_pipeline.py`, `src/agent_speak/sessions.py`, `src/agent_speak/pipeline.py`, `src/agent_speak/config.py`.

- [ ] Add tests for `PlatformError` producing `stage.failed`, bounded events/subscriber queues/session count, and bounded artifact retention.
- [ ] Run focused tests and confirm each bound/event is missing.
- [ ] Emit sanitized stage failures consistently; add practical configurable bounds and oldest-first cleanup.
- [ ] Re-run focused tests and confirm they pass.

### Task 5: TTS PCM-WAV validation

**Files:** `tests/test_audio.py`, `tests/test_stage_api.py`, `tests/test_sessions_pipeline.py`, `src/agent_speak/audio.py`, `src/agent_speak/pipeline.py`, `src/agent_speak/app.py`.

- [ ] Add tests rejecting malformed, oversized, unsupported, and over-duration TTS bytes before artifact creation/serving.
- [ ] Run focused tests and confirm invalid provider bytes are persisted.
- [ ] Reuse bounded PCM-WAV decoding at the artifact boundary before atomic private writes.
- [ ] Re-run focused tests and confirm they pass.

### Task 6: WebUI bounds and processing controls

**Files:** `tests/test_webui.py`, `web/app.js`, `web/index.html`.

- [ ] Add source-contract tests for 30-second auto-stop, early source/converted-size validation, and disabling recording plus upload throughout processing.
- [ ] Run focused tests and confirm hooks/copy are absent.
- [ ] Add timer cleanup, exact configured bounds, early file/blob checks, and a shared processing-control function without changing layout.
- [ ] Re-run focused tests and confirm they pass.

### Task 7: Ignore rules, status semantics, and endpoint documentation

**Files:** `tests/test_operations.py`, `.gitignore`, `scripts/status.sh`, `README.md`, `spec/API.md`, `spec/RUNTIME.md`, `spec/UI.md`, `.env.example`.

- [ ] Add tests for all requested private model/audio extensions, nonzero stopped status, and informational endpoint documentation.
- [ ] Run focused tests and confirm missing patterns/semantics.
- [ ] Extend ignore rules, return nonzero for stopped service, and update operator/API documentation.
- [ ] Re-run focused tests and confirm they pass.

### Task 8: Full verification

**Files:** all changed files.

- [ ] Run the complete pytest suite and require zero failures.
- [ ] Run shell syntax checks and any project test wrapper that is practical offline.
- [ ] Inspect `git diff` and `git status` for accidental feature/layout regressions and generated private artifacts.
