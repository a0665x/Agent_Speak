# Realtime Model Reliability and Diagnostic Logging Design

## Goal

Make model selection deterministic, restore realtime Breeze transcripts, verify the Qwen event path, and provide privacy-preserving logs that support future diagnosis without recording audio or recognized text.

## Confirmed failure evidence

- Breeze partial and final worker requests return HTTP 500 while Whisper requests return HTTP 200.
- Qwen worker requests return HTTP 200 and its native result object exposes a `text` field.
- The UI currently owns selected model, runtime model catalog, and switching state separately, so a stale catalog response can overwrite or contradict a newer user selection.
- Provider exceptions are converted into bounded API errors, but no structured internal diagnostic record preserves exception type, stage, model, or latency.

## Model selection contract

The UI tracks two distinct values:

- `requested`: the newest selection made by the user and shown immediately by the selector and Active Models row.
- `confirmed`: the worker model reported as `ready`, with no pending request.

Each switch receives a monotonically increasing generation. Catalog responses from an older generation cannot mutate the current selection. While a request is loading, both model rows show the requested target and a spinner. `Ready` is shown only when the runtime model and correction model exactly match the requested values. A failed request rolls both controls and rows back to the latest confirmed values.

## ASR output contract

All selectable providers return a non-empty Python string to `ASRModelManager`. The worker normalizes this to `{text, device, mode, asr_model}`. The gateway emits `asr.partial` and `asr.final` with `data.text`, and the UI reducer renders both event types.

Breeze uses a Whisper model loaded in half precision on CUDA. Floating processor tensors must be moved to both the model device and model floating dtype; integer tensors retain their dtype. Qwen continues using its native `(numpy_array, sample_rate)` API, with regression coverage for its object-shaped result and the normalized realtime events.

## Diagnostic logging contract

Gateway and ASR worker logs use one JSON object per line. They are written to stdout and to the separately owned rotating files `runtime/logs/gateway.jsonl` and `runtime/asr-worker/logs/asr-worker.jsonl`. File logs rotate at a bounded size and retain a bounded number of backups. Environment settings control level, size, and backup count.

Levels:

- `ERROR`: unexpected exceptions, unrecoverable model activation failure, transport failure.
- `WARNING`: provider retry, empty transcript, queue saturation, recoverable ASR/correction failure.
- `INFO`: service lifecycle, model activation lifecycle, anonymized session lifecycle, endpoint completion.
- `DEBUG`: queue depth, state transitions, durations, retry counters.

Allowed structured fields include `timestamp`, `level`, `service`, `event`, `request_id`, anonymized `session_ref`, `stage`, `model`, `device`, `mode`, `duration_ms`, `queue_depth`, `error_code`, `exception_type`, and retry counters.

Logs must never contain raw audio, audio encodings, transcript or correction text, device labels, credentials, authorization headers, cookies, full request bodies, full exception messages, filesystem secrets, or raw session identifiers. Session references are one-way shortened hashes. Public error responses remain bounded and do not expose internal exception details.

`./run.sh --logs [all|gateway|asr-worker|correction-worker]` is the supported first diagnostic command. Gateway and ASR worker output contains the structured diagnostics defined here; the externally supplied correction container retains its native process-log format. The troubleshooting sequence is status, filtered logs, model catalog, then tests.

## Compatibility

The `/api/v1` response and WebSocket event contracts remain unchanged. Logging is an internal observability addition. No microphone or speaker is started by diagnostics or tests.
