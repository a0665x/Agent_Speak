from __future__ import annotations

import json
import logging

from agent_speak.diagnostic_logging import configure_diagnostic_logging, log_event, session_reference


def test_session_reference_is_stable_and_does_not_expose_raw_identifier() -> None:
    raw = "private-session-123"

    first = session_reference(raw)

    assert first == session_reference(raw)
    assert raw not in first
    assert len(first) == 12


def test_structured_log_uses_allowlisted_fields_and_hides_payloads(tmp_path) -> None:
    logger = configure_diagnostic_logging(
        service="gateway-test",
        runtime_dir=tmp_path,
        level="DEBUG",
        max_bytes=16_384,
        backup_count=2,
        stream=False,
    )

    log_event(
        logger,
        logging.WARNING,
        "asr.failed",
        session_id="private-session-123",
        stage="asr",
        model="breeze-asr-25",
        duration_ms=12.5,
        error=RuntimeError("secret transcript and filesystem path"),
        text="recognized private words",
        audio=b"private audio",
        authorization="Bearer credential",
    )
    for handler in logger.handlers:
        handler.flush()

    payload = json.loads((tmp_path / "logs" / "gateway-test.jsonl").read_text(encoding="utf-8"))
    rendered = json.dumps(payload)
    assert payload["service"] == "gateway-test"
    assert payload["event"] == "asr.failed"
    assert payload["level"] == "WARNING"
    assert payload["session_ref"] == session_reference("private-session-123")
    assert payload["exception_type"] == "RuntimeError"
    assert payload["model"] == "breeze-asr-25"
    assert payload["duration_ms"] == 12.5
    assert "private-session-123" not in rendered
    assert "recognized private words" not in rendered
    assert "private audio" not in rendered
    assert "credential" not in rendered
    assert "secret transcript" not in rendered


def test_file_handler_uses_bounded_rotation_settings(tmp_path) -> None:
    logger = configure_diagnostic_logging(
        service="asr-worker-test",
        runtime_dir=tmp_path,
        level="INFO",
        max_bytes=2_048,
        backup_count=3,
        stream=False,
    )

    handler = logger.handlers[0]

    assert handler.maxBytes == 2_048  # type: ignore[attr-defined]
    assert handler.backupCount == 3  # type: ignore[attr-defined]
