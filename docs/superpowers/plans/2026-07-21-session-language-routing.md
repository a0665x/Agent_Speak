# Session-Frozen Speech Language Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` for every behavior change and `verification-before-completion` before claiming completion. If the user chooses delegated execution, use `subagent-driven-development`; for inline execution, follow this plan in order.

**Goal:** Make each realtime session use one immutable spoken-language policy for ASR, endpoint detection, and transcript correction, while keeping one loaded multilingual Whisper model and one loaded multilingual Qwen model.

**Architecture:** Add a small language-contract module, persist the public language value on `SessionSummary`, and copy it into every realtime inference job. The ASR worker maps the public value to a request-time Faster-Whisper hint; the Gateway selects locale-specific endpoint and correction prompts. The React UI keeps presentation locale and pending speech language as separate state, snapshots the latter when creating a session, and exposes the locked language throughout that session.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, Faster-Whisper, llama.cpp/Qwen, asyncio queues, React 19, TypeScript, Vitest, pytest, Docker Compose.

---

## Guardrails

- Work directly on the current `main`, as previously authorized, without creating a worktree.
- Do not start microphone capture or speaker playback during implementation or verification.
- Preserve all existing `/api/v1` endpoint paths and the external `listen_once → Agent reasoning/tools → speak` contract.
- Keep `POST /api/v1/audio/asr`, MCP tools, full-turn behavior, TTS, and configured provider defaults backward compatible.
- Do not download or commit model weights. The existing multilingual Faster-Whisper `small` and Qwen2.5 model are reused.
- Never stage `.env`, credentials, recordings, features/voiceprints, databases, runtime files, model weights, logs, `.superpowers/`, or Agent-private state.

## Task 1: Define and persist the public session language contract

**Files:**

- Create: `src/agent_speak/speech_languages.py`
- Modify: `src/agent_speak/schemas.py`
- Modify: `src/agent_speak/sessions.py`
- Modify: `src/agent_speak/app.py`
- Test: `tests/test_app.py`
- Test: `tests/test_sessions_pipeline.py`

### Step 1: Write failing API and broker tests

Add tests proving:

- `POST /api/v1/sessions` defaults to `speech_language: "zh-TW"`;
- `POST /api/v1/sessions?speech_language=auto|en|zh-TW|ja|ko` preserves the exact public value in both create and subsequent GET responses;
- an unsupported value returns the existing stable HTTP 422 envelope;
- `session.created` includes the frozen language so event consumers can audit the policy;
- the broker cannot mutate the language because it exposes no language setter.

Run:

```bash
pytest -q tests/test_app.py tests/test_sessions_pipeline.py
```

Expected: FAIL because session creation has no language parameter or response field.

### Step 2: Add the shared language types and mappings

Create `speech_languages.py` with one public literal and explicit helpers:

```python
SpeechLanguage = Literal["auto", "en", "zh-TW", "ja", "ko"]
DEFAULT_SPEECH_LANGUAGE: SpeechLanguage = "zh-TW"

def whisper_language(value: SpeechLanguage) -> str | None:
    return {"auto": None, "en": "en", "zh-TW": "zh", "ja": "ja", "ko": "ko"}[value]
```

Do not accept aliases such as `zh`, `cn`, or arbitrary BCP-47 tags at this boundary.

### Step 3: Persist language in the session model

- Add `speech_language: SpeechLanguage` to `SessionSummary` with default `zh-TW` for backward-compatible internal construction.
- Change `SessionBroker.create` to accept a keyword-only `speech_language` argument, store it at creation, and include it in `session.created` event data.
- Do not add a mutation method.

### Step 4: Expose the optional query parameter

Change only `POST /api/v1/sessions` to accept:

```python
speech_language: SpeechLanguage = DEFAULT_SPEECH_LANGUAGE
```

Pass it to the broker. Leave `/api/v1/audio/asr`, `/turns`, and MCP entry points unchanged.

### Step 5: Run focused tests and commit

```bash
pytest -q tests/test_app.py tests/test_sessions_pipeline.py
git diff --check
git add src/agent_speak/speech_languages.py src/agent_speak/schemas.py src/agent_speak/sessions.py src/agent_speak/app.py tests/test_app.py tests/test_sessions_pipeline.py
git commit -m "feat: freeze speech language per session"
```

Expected: focused tests PASS and no whitespace errors.

## Task 2: Route request-time language through the shared ASR worker

**Files:**

- Modify: `src/agent_speak/production.py`
- Modify: `src/agent_speak/asr_worker.py`
- Modify: `src/agent_speak/remote_asr.py`
- Test: `tests/test_production_providers.py`
- Test: `tests/test_asr_worker.py`
- Test: `tests/test_remote_asr.py`

### Step 1: Write failing provider and worker tests

Add tests proving:

- one warmed `FasterWhisperASR` instance can transcribe successive requests using `en`, `zh`, `ja`, `ko`, and `None` hints without reloading its model;
- internal `speech_language=zh-TW` maps to Faster-Whisper `zh`;
- internal `speech_language=auto` maps to `None`;
- `RemoteASRProvider.transcribe_mode(..., speech_language)` sends the public value as a query parameter and injected-request field;
- legacy `transcribe(audio)` and `transcribe_mode(audio, mode)` continue to use the configured server default;
- an unsupported internal language is rejected with HTTP 422 before model inference.

Run:

```bash
pytest -q tests/test_production_providers.py tests/test_asr_worker.py tests/test_remote_asr.py
```

Expected: FAIL because ASR language is constructor-only and the worker accepts only `mode`.

### Step 2: Make Faster-Whisper language request-scoped

- Keep the configured constructor language as `default_language`.
- Extend `transcribe(audio, language=None, *, use_default=True)` or an equivalently clear API so legacy calls retain the configured default while explicit realtime calls may pass `None` for auto-detection.
- Pass the resolved value to `model.transcribe(language=...)`.
- Do not reconstruct or warm the model per request.

Use an explicit sentinel if necessary to distinguish “argument omitted” from the intentional `None` auto-detect hint.

### Step 3: Extend the internal worker boundary

- Add a typed optional `speech_language` query parameter to `/internal/v1/asr`.
- When omitted, call the legacy configured-default path.
- When provided, map the public value through `whisper_language` and pass the resulting hint to the same provider instance.
- Keep `mode` validation and audio bounds unchanged.

### Step 4: Extend the remote provider without breaking callers

Change `transcribe_mode` to accept an optional third argument. Include it only when explicitly supplied:

```python
transcribe_mode(audio, mode, speech_language=None)
```

Use an omission sentinel internally so `None` does not collide with a public language value. Continue sending no language parameter for general pipeline calls.

### Step 5: Run focused tests and commit

```bash
pytest -q tests/test_production_providers.py tests/test_asr_worker.py tests/test_remote_asr.py
git diff --check
git add src/agent_speak/production.py src/agent_speak/asr_worker.py src/agent_speak/remote_asr.py tests/test_production_providers.py tests/test_asr_worker.py tests/test_remote_asr.py
git commit -m "feat: route language hints to shared asr"
```

## Task 3: Carry the frozen language through every realtime job

**Files:**

- Modify: `src/agent_speak/realtime_queue.py`
- Modify: `src/agent_speak/realtime.py`
- Modify: `src/agent_speak/realtime_routes.py`
- Test: `tests/test_realtime_queue.py`
- Test: `tests/test_realtime.py`
- Test: `tests/test_realtime_websocket.py`

### Step 1: Write failing propagation tests

Add tests proving:

- `ASRJob` and `TextJob` require a `speech_language`;
- opening a realtime WebSocket retrieves the existing session language once and freezes it into the stream;
- partial and final ASR calls receive that exact value;
- endpoint and correction calls receive that exact value;
- reconnecting to the same stored session retains its original value;
- no control frame can mutate it.

Use fake providers that record `(mode, speech_language)` and avoid hardware.

Run:

```bash
pytest -q tests/test_realtime_queue.py tests/test_realtime.py tests/test_realtime_websocket.py
```

Expected: FAIL because queues and coordinator currently carry only text/audio and mode.

### Step 2: Extend immutable jobs and stream construction

- Add `speech_language: SpeechLanguage` to `ASRJob` and `TextJob`.
- Change `RealtimeCoordinator.open(session_id, speech_language)` and `RealtimeStream(...)` to require the frozen value.
- In `realtime_routes.py`, fetch the `SessionSummary` and pass its stored language when opening the stream.
- When the coordinator returns an existing stream, verify its language matches the stored session; treat mismatch as an internal programming error rather than silently changing it.

### Step 3: Forward language to inference calls

- Call `asr.transcribe_mode(wav, job.mode, job.speech_language)`.
- Call `text.detect(job.current_text, job.speech_language)`.
- Call `text.revise(job.previous_text, job.current_text, job.speech_language)`.
- Populate every job from `self.speech_language`.

Update `RealtimeTextAdapter` to accept the optional language argument while keeping fallback providers compatible. If an older correction/endpoint provider lacks language-aware methods, the adapter may call its existing signature; the production Qwen provider must use the language.

### Step 4: Run focused tests and commit

```bash
pytest -q tests/test_realtime_queue.py tests/test_realtime.py tests/test_realtime_websocket.py
git diff --check
git add src/agent_speak/realtime_queue.py src/agent_speak/realtime.py src/agent_speak/realtime_routes.py tests/test_realtime_queue.py tests/test_realtime.py tests/test_realtime_websocket.py
git commit -m "feat: propagate session language in realtime jobs"
```

## Task 4: Localize endpoint and correction policy for Qwen

**Files:**

- Modify: `src/agent_speak/text_inference.py`
- Modify: `src/agent_speak/realtime.py`
- Test: `tests/test_text_inference.py`
- Test: `tests/test_realtime.py`

### Step 1: Write failing prompt and fallback tests

Parameterize all five public values and assert:

- the system prompt identifies the requested language policy;
- `zh-TW` explicitly requires Traditional Chinese output;
- `auto` is conservative and does not claim a single script;
- strict JSON schema, `temperature: 0`, token protection, edit-distance limits, and raw-text fallback remain unchanged;
- language-specific incomplete examples/markers stay incomplete on invalid worker output.

Include representative continuation endings:

- English: `because`, `so`, `but`, `and`, `if`, `then`;
- Traditional Chinese: `因為`, `所以`, `但是`, `然後`, `如果`, `以及`;
- Japanese: `ので`, `から`, `でも`, `そして`, `もし`, `また`;
- Korean: `때문에`, `그래서`, `하지만`, `그리고`, `만약`, `또한`.

Run:

```bash
pytest -q tests/test_text_inference.py
```

Expected: FAIL because prompts and markers are Chinese-only and signatures have no language argument.

### Step 2: Add explicit policy catalogs

Replace global single-language prompt strings with dictionaries keyed by `SpeechLanguage`. Export one small helper such as `ends_with_continuation(text, language)` for the realtime fallback.

Keep prompts narrowly scoped: endpoint decides only completion; correction fixes recognition, spacing, script-appropriate punctuation, and sentence boundaries without answering, summarizing, or inventing facts.

Replace the inline Chinese-only continuation tuple in `RealtimeStream._accept_text_result` with this helper so invalid/failed endpoint responses remain conservative for all five language policies.

### Step 3: Make provider calls language-aware

Use default `zh-TW` parameters for backward compatibility:

```python
detect(text, speech_language="zh-TW")
revise(previous_text, current_text, speech_language="zh-TW")
```

Keep `correct(text)` on the configured compatibility default because general REST/MCP correction does not own a realtime session language.

### Step 4: Run focused tests and commit

```bash
pytest -q tests/test_text_inference.py tests/test_realtime.py
git diff --check
git add src/agent_speak/text_inference.py tests/test_text_inference.py tests/test_realtime.py
git commit -m "feat: localize realtime text inference policy"
```

## Task 5: Add separate pending and locked speech-language state to React

**Files:**

- Create: `frontend/realtime/src/speechLanguage.ts`
- Create: `frontend/realtime/src/components/SpeechLanguageControl.tsx`
- Modify: `frontend/realtime/src/App.tsx`
- Modify: `frontend/realtime/src/i18n.tsx`
- Modify: `frontend/realtime/src/styles.css`
- Test: `frontend/realtime/src/App.test.tsx`
- Create: `frontend/realtime/src/speechLanguage.test.ts`

### Step 1: Write failing state and interaction tests

Cover:

- initial pending speech language follows UI locale;
- explicit override persists under a separate key such as `agent-speak-speech-language`;
- after override, changing presentation locale no longer changes pending speech language;
- `auto` persists as a real explicit choice;
- Start calls `/api/v1/sessions?speech_language=` with the selected value encoded by `URLSearchParams`;
- the returned session language becomes the locked display value;
- changing the selector while active updates pending state only, leaves client/session/transcript/graph state intact, and shows localized “Applies to the next session” feedback;
- Stop does not erase the completed session's locked language;
- the next Start uses the new pending value.

Mock `fetch`, device readiness, and `RealtimeClient`; do not request browser microphone permission in tests.

Run:

```bash
npm --prefix frontend/realtime test -- src/speechLanguage.test.ts src/App.test.tsx
```

Expected: FAIL because speech language is not distinct from presentation locale.

### Step 2: Implement the pure speech-language state helpers

In `speechLanguage.ts` define:

- `SPEECH_LANGUAGES = ['auto', 'en', 'zh-TW', 'ja', 'ko']`;
- a typed parser that rejects corrupt storage;
- locale-to-default mapping (`en → en`, `zh-TW → zh-TW`, `ja → ja`, `ko → ko`);
- load/persist helpers that record whether the user explicitly overrode the default.

Keep all storage access guarded for privacy/incognito failures.

### Step 3: Build the accessible selector

Add `SpeechLanguageControl` inside the Device Gate/control deck with:

- a visible localized label;
- Auto detect, English, 繁體中文, 日本語, 한국어 options;
- at least 44 px control height and keyboard-visible focus;
- a locked-session chip while active or completed;
- a localized next-session note only when pending differs from locked during an active session.

Use the existing Apple-like color, radius, motion, and reduced-motion tokens. Avoid adding another dependency.

### Step 4: Wire session-frozen behavior

- Derive pending speech language from locale until an explicit override occurs.
- Create the session with an encoded query parameter.
- Read `speech_language` from the response and store it as `lockedSpeechLanguage`.
- Never alter `lockedSpeechLanguage` or restart `RealtimeClient` when either selector changes.
- Keep the existing device-ready gate: Start remains disabled until both microphone and output are confirmed.

### Step 5: Complete all four locale catalogs

Add matching keys for selector label, auto option, locked language, and next-session feedback to English, Traditional Chinese, Japanese, and Korean. Preserve the catalog-completeness test.

### Step 6: Run frontend tests/build and commit

```bash
npm --prefix frontend/realtime test
npm --prefix frontend/realtime run build
git diff --check
git add frontend/realtime/src/speechLanguage.ts frontend/realtime/src/speechLanguage.test.ts frontend/realtime/src/components/SpeechLanguageControl.tsx frontend/realtime/src/App.tsx frontend/realtime/src/i18n.tsx frontend/realtime/src/styles.css frontend/realtime/src/App.test.tsx
git commit -m "feat: add session-frozen speech language control"
```

## Task 6: Localize the OpenAPI contract and update project guidance

**Files:**

- Modify: `src/agent_speak/locales.py`
- Modify: `tests/test_app.py`
- Modify: `README.md`
- Modify: `spec/PROJECT_MAP.md`
- Modify: `spec/SKILL_AND_MCP.md`
- Modify: `skills/agent-speak/SKILL.md`

### Step 1: Write failing localized OpenAPI tests

For `en`, `zh-TW`, `ja`, and `ko`, assert that:

- the create-session endpoint explains `speech_language` and session freezing;
- the query parameter title/description and allowed values are present;
- `SessionSummary.speech_language` has a fully localized field description;
- response examples show the new field;
- the general ASR and MCP descriptions explicitly remain server-default behavior, not browser-locale behavior.

Run:

```bash
pytest -q tests/test_app.py -k 'openapi or session'
```

Expected: FAIL because localization metadata has no speech-language entries.

### Step 2: Add complete locale metadata

Extend the existing `locales.py` catalogs rather than bypassing the localized OpenAPI generator. Keep English as the docs default and maintain catalog-completeness assertions.

### Step 3: Update user and Agent documentation

Document:

- the five public values and `POST /api/v1/sessions?speech_language=...`;
- the frozen-per-session rule;
- the distinction between UI locale, speech language, and configured defaults;
- `zh-TW → zh` and `auto → model detection` mappings;
- no additional ASR/correction downloads are required;
- TTS voice selection is outside this feature;
- external Agents still use `listen_once → reason/tools → speak`.

Do not imply the built-in development echo provider is a real LLM.

### Step 4: Run docs/API tests and commit

```bash
pytest -q tests/test_app.py
git diff --check
git add src/agent_speak/locales.py tests/test_app.py README.md spec/PROJECT_MAP.md spec/SKILL_AND_MCP.md skills/agent-speak/SKILL.md
git commit -m "docs: explain multilingual session routing"
```

## Task 7: Full verification and safe runtime handoff

**Files:**

- Modify only if verification exposes a regression.

### Step 1: Run focused backend and frontend suites

```bash
pytest -q tests/test_app.py tests/test_sessions_pipeline.py tests/test_production_providers.py tests/test_asr_worker.py tests/test_remote_asr.py tests/test_realtime_queue.py tests/test_realtime.py tests/test_realtime_websocket.py tests/test_text_inference.py
npm --prefix frontend/realtime test
npm --prefix frontend/realtime run build
```

Expected: all PASS.

### Step 2: Run the repository-required regression

```bash
./run.sh --test
```

Expected: backend, recorder, and frontend tests all PASS. This command must not request microphone permission or play audio.

### Step 3: Review the complete patch and repository safety

```bash
git diff --check
git status --short
git diff --stat HEAD~6..HEAD
git log --oneline -8
```

Confirm only intended source, tests, specs, and public docs are committed. Confirm `.superpowers/` and all prohibited artifacts remain untracked/uncommitted.

### Step 4: Rebuild and inspect without starting listening

```bash
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --rebuild
./run.sh --status
curl -fsS 'http://127.0.0.1:8765/api/v1/health'
curl -fsS -X POST 'http://127.0.0.1:8765/api/v1/sessions?speech_language=en'
curl -fsS 'http://127.0.0.1:8765/openapi.json?lang=en'
curl -fsS 'http://127.0.0.1:8765/asr_realtime?lang=en'
```

Verify health, the returned frozen `speech_language`, localized OpenAPI metadata, and the static UI shell. Do not press Start Listening and do not invoke TTS.

### Step 5: Final commit only if verification required fixes

If any verification-only fix was needed, rerun its failing test first, then:

Stage each verified fix by its exact path as shown by `git status --short`, then run `git diff --cached --check` and commit it as `fix: complete multilingual session routing`. Never use `git add .` or stage unrelated pre-existing files.

Do not push unless GitHub authentication is confirmed and the user explicitly asks to publish this new change. Report the local commit hashes, tests, live URL `http://127.0.0.1:8765/asr_realtime`, and any remaining push/auth blocker accurately.
