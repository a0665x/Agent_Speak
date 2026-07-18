# API

Base path: `/api/v1`.

Core: `GET /health`, `GET /capabilities`, `POST /sessions`, `GET /sessions/{id}`, `WS /sessions/{id}/events`, `POST /sessions/{id}/turns`.

Stages: `POST /audio/vad`, `/audio/asr`, `/text/correct`, `/text/end-detect`, `/agent/respond`, `/tts/synthesize`.

Speakers: `POST/GET /speakers`, `GET/DELETE /speakers/{id}`, `POST /speakers/{id}/samples`, `POST /speakers/match`.

Artifacts: `GET /artifacts/{name}`. Failures use `{error:{code,message,stage,retryable,details}}`. `/docs` is field-level truth.
