# Realtime Model Reliability and Diagnostic Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make selectable ASR models update atomically, produce realtime transcript events, and emit privacy-safe structured diagnostics.

**Architecture:** Separate requested and confirmed UI model state with generation guards. Normalize provider tensors/results at the ASR boundary. Add a shared JSON logger used by gateway and worker, with bounded rotating files and a `run.sh` reader.

**Tech Stack:** React 18, TypeScript, Vitest, Python 3.11, FastAPI, pytest, Transformers, Docker Compose.

---

### Task 1: Guard model selection against stale responses

**Files:**
- Modify: `frontend/realtime/src/App.tsx`
- Modify: `frontend/realtime/src/components/ActiveModels.tsx`
- Test: `frontend/realtime/src/App.test.tsx`

- [ ] Add a failing test that delays an older catalog response, selects Breeze once, resolves the stale response, and asserts the selector and ASR row remain Breeze while loading.
- [ ] Run `npm test -- App.test.tsx` from `frontend/realtime` and confirm the stale response changes the displayed model.
- [ ] Add a synchronous switch generation ref and requested/confirmed selection state; apply catalog responses only to the generation that requested them.
- [ ] Assert `Ready` only appears when the catalog runtime models equal the requested models and no request is pending.
- [ ] Run `npm test -- App.test.tsx modelPresentation.test.ts` and confirm all model-selection tests pass.

### Task 2: Normalize Breeze CUDA inputs

**Files:**
- Modify: `src/agent_speak/asr_providers.py`
- Test: `tests/test_asr_providers.py`

- [ ] Add a failing test with floating and integer tensor doubles that expects floating input features to receive both the model device and floating dtype while integer masks only move device.
- [ ] Run `pytest tests/test_asr_providers.py -q` and confirm the dtype assertion fails.
- [ ] Extend the input movement helper to accept a floating dtype and cast only floating tensors; pass the Breeze model dtype from `transcribe`.
- [ ] Run `pytest tests/test_asr_providers.py tests/test_asr_worker.py -q` and confirm the adapter and worker tests pass.

### Task 3: Prove Qwen reaches the UI event contract

**Files:**
- Modify: `tests/test_asr_providers.py`
- Modify: `tests/test_realtime.py`
- Modify: `frontend/realtime/src/state/reducer.test.ts`

- [ ] Add provider coverage for the native Qwen result object and non-empty normalized string.
- [ ] Add a coordinator test asserting a Qwen-selected final result emits `asr.final` with `data.text` and `asr_model`.
- [ ] Add a reducer test asserting Qwen partial/final events create and update a transcript row.
- [ ] Run the three focused test files and confirm the event path passes without using a microphone.

### Task 4: Add privacy-safe structured logging

**Files:**
- Create: `src/agent_speak/diagnostic_logging.py`
- Modify: `src/agent_speak/config.py`
- Modify: `src/agent_speak/app.py`
- Modify: `src/agent_speak/asr_worker.py`
- Modify: `src/agent_speak/realtime.py`
- Modify: `compose.yaml`
- Test: `tests/test_diagnostic_logging.py`
- Test: `tests/test_asr_worker.py`

- [ ] Add failing tests for JSON fields, session hashing, rotating-file configuration, and redaction of transcript/audio/session values.
- [ ] Run `pytest tests/test_diagnostic_logging.py -q` and confirm the logger module is missing.
- [ ] Implement JSON formatting, stdout plus rotating handlers, request IDs, anonymized session references, and environment-driven level/rotation settings.
- [ ] Add lifecycle and failure events at model activation, ASR execution, realtime queue, and exception boundaries; record exception class but not message or payload.
- [ ] Mount `runtime/` into the ASR worker and configure distinct service log filenames.
- [ ] Run focused logging, worker, realtime, and API tests and confirm public error bodies remain unchanged.

### Task 5: Add the log operator command and project documentation

**Files:**
- Modify: `run.sh`
- Modify: `README.md`
- Modify: `spec/RUNTIME.md`
- Modify: `spec/TESTING.md`
- Modify: `spec/PROJECT_MAP.md`
- Test: `tests/test_run_script.py`

- [ ] Add a failing run-script test for `--logs`, its service allowlist, and invalid target handling.
- [ ] Implement `./run.sh --logs [all|gateway|asr-worker]` using bounded Docker Compose tail output.
- [ ] Document log levels, fields, privacy exclusions, rotation, configuration, and the status → logs → catalog → tests troubleshooting sequence.
- [ ] Run `bash -n run.sh` and the run-script tests.

### Task 6: Build and verify the complete system

**Files:**
- Modify generated frontend assets under `web/asr_realtime/` through the existing build command only.

- [ ] Run the complete frontend test suite.
- [ ] Run `AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --test` and confirm all backend and frontend tests pass.
- [ ] Run `git diff --check` and inspect `git status -sb`; do not stage `.superpowers/`, runtime data, logs, models, or credentials.
- [ ] Rebuild/restart with the existing `run.sh` flow, verify `/api/v1/health`, `/api/v1/models`, and `/asr_realtime` without activating audio devices.
