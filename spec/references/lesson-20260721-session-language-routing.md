# Session-Frozen Speech Language Routing

Date: 2026-07-21
Status: Implemented

## Outcome

Realtime speech processing now uses a language policy that belongs to the API
session, rather than treating the Web UI presentation locale as pipeline state.
One multilingual Faster-Whisper `small` model and one multilingual Qwen2.5
correction worker are reused for all supported policies; selecting another
language does not download or load a language-specific model.

This change applies to `/asr_realtime`. It does not change the language behavior
of standalone `/api/v1/audio/asr`, full-turn processing, or MCP `listen_once`,
which continue to use the configured server default.

## Public contract

`POST /api/v1/sessions` accepts an optional `speech_language` query parameter:

| Public value | Faster-Whisper hint | Text policy |
| --- | --- | --- |
| `auto` | `None` (model detection) | Conservative multilingual |
| `en` | `en` | English |
| `zh-TW` | `zh` | Traditional Chinese |
| `ja` | `ja` | Japanese |
| `ko` | `ko` | Korean |

Omitting the parameter defaults to `zh-TW` for compatibility. Unsupported
values use the normal FastAPI HTTP 422 validation response.

The resolved public value is returned as `SessionSummary.speech_language` and
included in `session.created`. It is immutable for the lifetime of that session.
There is deliberately no endpoint for mutating it.

## Ownership and data flow

```text
presentation locale ──initial default──▶ pending speech language
                                             │
                                             ▼ Start Listening
POST /sessions?speech_language=… ──▶ immutable Session.speech_language
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     ▼                       ▼                       ▼
                ASR queue job          endpoint policy       correction policy
                     │                       │                       │
                     ▼                       └──────────┬────────────┘
          request-time Whisper hint                    ▼
                                              shared Qwen worker
```

The realtime stream snapshots the session value when it opens. Every ASR,
endpoint, and correction job carries the same value. A mismatch between an open
stream and its session is a programming error, not a request to switch policy.
This prevents partial hypotheses from changing language behavior midway through
an utterance.

`auto` enables ASR detection but does not rewrite the stored session value to a
detected language. Endpoint and correction therefore use the conservative
multilingual policy for the complete session.

## Model behavior and safety

Faster-Whisper chooses its language hint at each transcription call while keeping
one cached model instance. The correction worker keeps the existing Qwen2.5
multilingual model and receives locale-specific endpoint and revision prompts.
Language-specific continuation markers help avoid prematurely completing a
sentence at the 900 ms endpoint candidate.

All existing correction guards remain mandatory: bounded timeout and output,
strict JSON handling, protected-token preservation, normalized edit-distance
checks, and raw final-ASR fallback. A language selection must never weaken these
guards or cause a model download during an active session.

TTS voice selection is independent and remains out of scope. The built-in Agent
provider remains a development echo; this feature must not be described as LLM
reasoning or direct Codex-session injection.

## UI contract

The presentation selector continues to control visible `en`, `zh-TW`, `ja`, and
`ko` copy. The separate Speech language selector offers `auto` plus those four
languages.

- Until the user explicitly overrides Speech language, it follows presentation
  locale.
- The explicit override is stored under `agent-speak-speech-language`, separately
  from presentation locale.
- Start Listening snapshots the pending value into the newly created API session
  and displays the locked value.
- Changing the selector while listening applies only to the next session. It must
  not restart capture, replace the active WebSocket, or clear transcripts and
  graph nodes.
- The control remains keyboard accessible with a minimum 44 px target and fully
  localized feedback.

Changing documentation or UI language never silently changes standalone API or
MCP inference behavior.

## Verification evidence

The implementation was verified on 2026-07-21 without starting browser capture
or speaker playback:

- focused backend regression: 84 tests passed;
- frontend regression: 10 files and 38 tests passed;
- TypeScript and Vite production build passed;
- rebuilt Docker regression: 214 backend tests plus 38 frontend tests, ending in
  `TESTS_OK`;
- no-cache production rebuild selected NVIDIA/CUDA ASR and NVIDIA correction,
  and the Gateway became healthy;
- live API inspection returned session language `en` in both the session response
  and `session.created`, exposed the five-value OpenAPI enum, and served the UI
  bundle containing the Speech language selector.

The focused regression lives in:

- `tests/test_sessions_pipeline.py`
- `tests/test_realtime.py`
- `tests/test_realtime_websocket.py`
- `tests/test_asr_worker.py`
- `tests/test_remote_asr.py`
- `tests/test_production_providers.py`
- `tests/test_text_inference.py`
- `tests/test_app.py`
- `frontend/realtime/src/**/*.test.ts*`

Hardware visibility and actual capture/playback remain separate acceptance
concerns. A healthy container or an enumerated device does not prove physical
recording or playback.

## Future change checklist

Before changing this behavior, verify all of the following:

1. Public enum values and the compatible `zh-TW` default remain synchronized
   across API schema, OpenAPI localization, UI, workers, and tests.
2. Session language remains frozen; active-stream mutation must require a new
   explicit contract and concurrency design.
3. Presentation locale, speech recognition policy, and TTS voice stay separate.
4. One loaded multilingual ASR/correction model remains the default architecture;
   any per-language workers need explicit GPU-memory and lifecycle justification.
5. Legacy standalone API, full-turn, and MCP behavior is tested independently.
6. Validation and raw-ASR safety fallbacks are preserved in every language.
7. Tests and documentation checks do not request microphone permission or play
   audio unless the user explicitly authorizes a hardware smoke test.

## Related specifications

- [`../API.md`](../API.md)
- [`../UI.md`](../UI.md)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../SKILL_AND_MCP.md`](../SKILL_AND_MCP.md)
- [`MODEL_STRATEGY.md`](MODEL_STRATEGY.md)
