"""Typed runtime configuration with a small, dependency-free env loader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65_535)
    data_dir: Path = Path("data")
    runtime_dir: Path = Path("runtime")
    max_audio_bytes: int = Field(default=8 * 1024 * 1024, ge=44, le=64 * 1024 * 1024)
    max_audio_seconds: float = Field(default=30.0, gt=0, le=300)
    vad_rms_threshold: float = Field(default=0.015, gt=0, lt=1)
    max_sessions: int = Field(default=100, ge=1, le=10_000)
    max_session_events: int = Field(default=128, ge=1, le=10_000)
    max_event_queue: int = Field(default=64, ge=1, le=10_000)
    max_artifacts: int = Field(default=100, ge=1, le=10_000)

    @classmethod
    def from_env(cls) -> "Settings":
        values: dict[str, Any] = {}
        for field in cls.model_fields:
            key = f"AGENT_SPEAK_{field.upper()}"
            if key in os.environ:
                values[field] = os.environ[key]
        return cls.model_validate(values)

    def prepare_directories(self) -> None:
        for directory in (self.data_dir, self.runtime_dir, self.runtime_dir / "artifacts"):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.chmod(0o700)
