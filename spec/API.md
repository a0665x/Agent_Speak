# API

Base path: `/api/v1`.

Core: `GET /health`, `GET /capabilities`, `POST /sessions`, `GET /sessions/{id}`, `WS /sessions/{id}/events`, `POST /sessions/{id}/turns`.

`POST /sessions/{id}/turns` and the audio stage endpoints accept a raw 16-bit PCM WAV request body (`Content-Type: audio/wav`). Ingress is counted while streaming and rejected as soon as the configured byte limit is crossed. A successful turn returns transcript, corrected text, endpoint decision, agent response, per-stage milliseconds, and a local `audio_url`. Session reads include bounded recent ordered event history; WebSocket connections replay that retained history and then stream new events through a bounded per-connection queue.

The endpoint `complete` decision is informational metadata in this MVP. A full-turn request continues through agent response and TTS whether `complete` is true or false; callers that need multi-utterance accumulation must make that decision before submitting a full turn.

Stages: `POST /audio/vad`, `/audio/asr`, `/text/correct`, `/text/end-detect`, `/agent/respond`, `/tts/synthesize`.

Speakers: `POST/GET /speakers`, `GET/PATCH/DELETE /speakers/{id}`, `POST /speakers/{id}/samples`, `POST /speakers/match`.

Speaker creates and updates use `{name,notes}` JSON. Enrollment/match use raw WAV. Every speaker response repeats that matching is convenience identification, not biometric authentication. Match scores are deterministic local acoustic similarity, not identity proof.

Artifacts: `GET /artifacts/{name}`. Failures use `{error:{code,message,stage,retryable,details}}`. `/docs` is field-level truth.

OpenAPI is also a beginner-facing contract. `/docs` groups operations under six Traditional Chinese tags (system, conversation flow, audio stages, text stages, speakers, audio artifacts). Every HTTP endpoint provides a Chinese summary and an explicit input/output description. Pydantic fields expose descriptions, defaults where applicable, and representative examples; binary request schemas state the required 16-bit PCM WAV format and the 8 MiB/30-second bounds. `/openapi.json` is the machine-readable source of the same contract.

Concurrent full turns for one session are rejected with HTTP 409 and stable code `turn_in_progress`; turns in different sessions may proceed concurrently. TTS output is validated as bounded uncompressed 16-bit PCM WAV before private artifact storage and again before serving. HTTP responses include CSP, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer` headers.

Audio is limited by `AGENT_SPEAK_MAX_AUDIO_BYTES` and `AGENT_SPEAK_MAX_AUDIO_SECONDS`. Supported WAV is uncompressed 16-bit PCM, mono/stereo, 8–48 kHz. Error codes include `invalid_wav`, `unsupported_wav`, `audio_too_large`, `audio_too_long`, `no_speech`, `stage_failed`, and resource-specific `*_not_found` codes.
