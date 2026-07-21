# Session-Frozen Speech Language Routing Design

**Date:** 2026-07-21

**Status:** Approved design

## Goal

Make the ASR, endpoint detection, and transcript-correction stages use the spoken language selected for a realtime session. The project continues to reuse one multilingual Faster-Whisper model and one multilingual Qwen model; this feature does not download one model per language.

## Scope

The feature covers realtime sessions created by `/asr_realtime`. It adds `auto`, English, Traditional Chinese, Japanese, and Korean speech-language choices and carries the selected value through realtime ASR, endpoint, and correction jobs.

The project-page language remains presentation state. The speech language initially follows it, but becomes independent after the user explicitly changes the speech-language selector. Existing bounded REST audio stages, MCP tools, Agent boundaries, TTS behavior, and provider identities remain unchanged.

## Selected Approach

Each session owns one immutable `speech_language`. The UI sends the selected language while creating a session. The Gateway stores it with the session and copies it into every ASR, endpoint, and correction job. Workers select request-time language behavior while retaining one loaded model instance.

This is preferred over one worker per language because duplicated workers would waste GPU memory and operational complexity. It is preferred over per-utterance automatic detection because short partials can cause unstable language decisions. `auto` remains an explicit option for users who need detection.

## Language Contract

Public values are:

- `auto`
- `en`
- `zh-TW`
- `ja`
- `ko`

The ASR mapping is:

| Session language | Faster-Whisper language |
| --- | --- |
| `auto` | `None` for model detection |
| `en` | `en` |
| `zh-TW` | `zh` |
| `ja` | `ja` |
| `ko` | `ko` |

The existing server default remains Traditional Chinese for compatibility. Clients that omit the parameter continue to create a valid session using `zh-TW`.

## Public API

Session creation accepts an optional query parameter:

```http
POST /api/v1/sessions?speech_language=en
```

The session response and subsequent session reads include `speech_language`:

```json
{
  "id": "session-id",
  "state": "created",
  "speech_language": "en"
}
```

Unknown values use FastAPI's existing HTTP 422 validation response. No endpoint mutates the language of an existing session. Existing clients and external Agents may omit the parameter.

The general `/api/v1/audio/asr` endpoint keeps the configured server default and does not inherit browser presentation state. This preserves the current external Agent and MCP contract.

## Realtime UI

The Device Gate area gains a visible, keyboard-accessible Speech language selector with a minimum 44 px target:

- Auto detect
- English
- 繁體中文
- 日本語
- 한국어

Before a manual override, changing the UI language also changes the pending speech language. After a manual override, UI language changes do not overwrite it. The explicit choice is stored separately from `agent-speak-locale`.

Starting Listening snapshots the pending language into the new session. The session chip displays the locked language. While Listening is active, changing the selector updates only the pending language and shows a localized “Applies to the next session” message. It never restarts capture, clears transcripts, changes graph nodes, or alters the active WebSocket.

On Stop, the completed session retains its locked language. The next Start creates a new session with the current pending language.

## Pipeline Data Flow

```text
UI locale ──default──▶ pending speech language
                           │
                           ▼ Start Listening
POST /sessions?speech_language=…
                           │
                           ▼
immutable Session.speech_language
      ├──▶ ASR job ──▶ request-time Whisper hint
      ├──▶ endpoint job ──▶ locale-specific completion prompt
      └──▶ correction job ──▶ locale-specific revision prompt
```

Realtime queue jobs carry the public session language. The ASR worker accepts the public value on each internal request and maps it to the Faster-Whisper hint. `FasterWhisperASR` keeps the loaded model cached and moves language selection from constructor-only state to the transcribe call.

The correction worker continues using the existing Qwen2.5-1.5B-Instruct GGUF. The Gateway chooses language-specific endpoint and revision system prompts, plus language-specific continuation markers, while retaining the existing strict JSON schemas, temperature, token bound, protected-token validation, normalized edit-distance guard, and raw-ASR fallback.

For `auto`, the ASR worker enables model language detection. Endpoint and correction use a conservative multilingual prompt based on the returned transcript; the session value itself remains `auto` and is never silently mutated.

## Language-Specific Text Behavior

- English corrects spelling, punctuation, spacing, and sentence boundaries without paraphrasing.
- Traditional Chinese corrects wrong characters, word boundaries, and punctuation and asks for Traditional Chinese output.
- Japanese corrects kana/kanji transcription, punctuation, and sentence completion without rewriting meaning.
- Korean corrects spelling, spacing, punctuation, and sentence completion without rewriting meaning.
- Auto uses conservative multilingual rules and avoids assuming a specific script.

Endpoint continuation markers are cataloged per language. Provider failure, timeout, invalid JSON, protected-token loss, or excessive edit distance continues to preserve raw ASR text.

## Error Handling

- An unsupported public `speech_language` produces HTTP 422.
- An unsupported internal ASR language produces a bounded 422 platform error.
- A missing session retains the existing 404 behavior.
- There is no active-session language mutation, so no partial transcript can change language policy mid-utterance.
- Automatic detection uncertainty does not change session configuration or trigger a model download.

## Testing

Hardware-free regression covers:

- all five session language values and the compatible default;
- session response/read serialization;
- immutable language across the WebSocket lifecycle;
- realtime job propagation;
- Whisper mappings, including `zh-TW → zh` and `auto → None`;
- request-time language changes with one cached ASR model instance;
- endpoint and correction prompts for all five values;
- preservation of existing safety fallbacks;
- UI-locale defaulting, explicit override persistence, session-frozen behavior, localized next-session feedback, and preservation of transcript/graph state;
- unchanged `/api/v1`, MCP, and provider-boundary tests.

The full Docker regression remains hardware-free and must not request microphone permission or play audio. Final live verification checks service health, model capabilities, and static/browser state without starting Listening.

## Model and Privacy Impact

No additional Faster-Whisper or Qwen weights are required. `small` is kept as the shared multilingual ASR model, and Qwen2.5 remains the shared multilingual text model. No speech-language selection, transcript, recording, model artifact, or runtime state is committed outside the existing safe public source and test fixtures.
