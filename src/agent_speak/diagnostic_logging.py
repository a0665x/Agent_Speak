"""Privacy-preserving structured diagnostics for gateway services."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


_ALLOWED_FIELDS = {
    "request_id",
    "session_ref",
    "stage",
    "model",
    "device",
    "mode",
    "duration_ms",
    "queue_depth",
    "error_code",
    "exception_type",
    "retry",
    "status_code",
    "method",
    "route",
    "state",
}


def session_reference(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12]


class DiagnosticJsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "event": getattr(record, "diagnostic_event", record.getMessage()),
        }
        fields = getattr(record, "diagnostic_fields", {})
        if isinstance(fields, dict):
            payload.update({key: value for key, value in fields.items() if key in _ALLOWED_FIELDS})
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_diagnostic_logging(
    *,
    service: str,
    runtime_dir: Path,
    level: str = "INFO",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    stream: bool = True,
) -> logging.Logger:
    logger = logging.getLogger(f"agent_speak.diagnostic.{service}")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()

    log_dir = Path(runtime_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    log_dir.chmod(0o700)
    log_path = log_dir / f"{service}.jsonl"
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    os.chmod(log_path, 0o600)
    formatter = DiagnosticJsonFormatter(service)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    if stream:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    session_id: str | None = None,
    error: BaseException | None = None,
    **fields: Any,
) -> None:
    safe = {key: value for key, value in fields.items() if key in _ALLOWED_FIELDS}
    if session_id:
        safe["session_ref"] = session_reference(session_id)
    if error is not None:
        safe["exception_type"] = type(error).__name__
    logger.log(
        level,
        event,
        extra={"diagnostic_event": event, "diagnostic_fields": safe},
    )
