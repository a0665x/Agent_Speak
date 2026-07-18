"""Domain errors mapped to the stable public error envelope."""

from __future__ import annotations

from typing import Any


class PlatformError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        stage: str | None = None,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.stage = stage
        self.retryable = retryable
        self.details = details or {}
