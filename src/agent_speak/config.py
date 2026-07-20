"""Typed runtime configuration with a small, dependency-free env loader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    accelerator: Literal["auto", "cpu", "nvidia"] = "auto"
    asr_model: str = "small"
    asr_language: str | None = "zh"
    asr_compute_type: str = "int8"
    asr_cuda_compute_type: str = "float16"
    asr_cpu_threads: int = Field(default=4, ge=1, le=32)
    tts_model_path: Path = Path("models/piper/zh_CN-huayan-medium.onnx")
    realtime_frame_ms: Literal[20, 40] = 20
    realtime_pre_roll_ms: int = Field(default=300, ge=0, le=2_000)
    realtime_min_speech_ms: int = Field(default=250, ge=20, le=5_000)
    realtime_partial_interval_ms: int = Field(default=800, ge=200, le=5_000)
    realtime_endpoint_ms: int = Field(default=900, ge=200, le=5_000)
    realtime_hard_endpoint_ms: int = Field(default=1_800, ge=400, le=10_000)
    realtime_endpoint_timeout_ms: int = Field(default=250, ge=50, le=2_000)
    realtime_max_utterance_seconds: float = Field(default=30.0, gt=0, le=300)
    realtime_partial_queue: int = Field(default=8, ge=1, le=128)
    realtime_final_queue: int = Field(default=8, ge=1, le=128)
    realtime_text_queue: int = Field(default=8, ge=1, le=128)
    realtime_expected_device: str = Field(default="Zone Vibe 100", min_length=1, max_length=200)
    asr_worker_url: str = ""
    correction_worker_url: str = ""
    correction_model: str = "Qwen2.5-1.5B-Instruct-Q4_K_M"
    effective_accelerator: Literal["cpu", "nvidia"] = "cpu"

    @model_validator(mode="after")
    def validate_realtime_contract(self) -> "Settings":
        if self.realtime_endpoint_ms >= self.realtime_hard_endpoint_ms:
            raise ValueError("realtime_endpoint_ms must be lower than realtime_hard_endpoint_ms")
        for name in ("asr_worker_url", "correction_worker_url"):
            value = getattr(self, name)
            if value and not value.startswith(("http://", "https://")):
                raise ValueError(f"{name} must be an HTTP(S) URL")
        return self

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
