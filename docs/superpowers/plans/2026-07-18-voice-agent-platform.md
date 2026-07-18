# Voice Agent Platform Implementation Plan

> For agentic workers: use TDD task-by-task and commit each independently testable slice.

Goal: Deliver a runnable local-first voice-agent API and responsive operator WebUI on Jetson AGX Orin.

Architecture: FastAPI orchestrates focused providers and session events. SQLite/files persist private runtime state. A static console consumes REST and WebSocket APIs.

Tech stack: Python 3.11, FastAPI, Pydantic, NumPy, SQLite, vanilla HTML/CSS/JS, pytest.

## Global constraints
- Target aarch64 Jetson AGX Orin and Python 3.11.
- Never commit secrets, recordings, embeddings, model weights, caches, or traces.
- Offline default providers identify themselves as development providers.
- Speaker matching is never described as authentication.
- UI is responsive, accessible, and includes loading/empty/error feedback.

## Task 1: Skeleton and contracts
Write failing settings/health/provider/error tests; implement config, schemas, provider protocols, app factory; run tests; commit.

## Task 2: Sessions and pipeline
Write failing event/order/timing/failure tests; implement broker, development providers, orchestrator, REST/WebSocket routes; run tests; commit.

## Task 3: Audio and speaker profiles
Write failing WAV/VAD/enrollment/match tests; implement bounded audio utilities, acoustic features, SQLite/file store and routes; run tests; commit.

## Task 4: Operator WebUI
Write route/static assertions; implement accessible console, recorder upload, events, status, capabilities, speakers; run tests; commit.

## Task 5: Operations and smoke
Add setup/run/status/test/health/mic/API smoke scripts; complete spec and README; run unit, API, microphone, browser/mobile, link, and Git-hygiene checks; commit.
