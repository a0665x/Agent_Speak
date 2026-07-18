"""Stable transport models shared by routes and pipeline code."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(StrictModel):
    code: str
    message: str
    stage: str | None = None
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(StrictModel):
    error: ErrorBody


class ProviderCapability(StrictModel):
    stage: Literal["vad", "asr", "correction", "endpoint", "agent", "tts"]
    name: str
    ready: bool
    development: bool
    limitations: list[str] = Field(default_factory=list)
    version: str = "builtin"
    device: str = "cpu"


class CapabilitiesResponse(StrictModel):
    providers: list[ProviderCapability]
    speaker_matching_notice: str = "Convenience identification only; not biometric authentication."


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    version: str
    storage_ready: bool


class PipelineEvent(StrictModel):
    sequence: int = Field(ge=1)
    type: str
    stage: str | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    elapsed_ms: float | None = Field(default=None, ge=0)
    data: dict[str, Any] = Field(default_factory=dict)


class SessionSummary(StrictModel):
    id: str
    state: str
    created_at: datetime
    events: list[PipelineEvent] = Field(default_factory=list)


class TextInput(StrictModel):
    text: str = Field(min_length=1, max_length=20_000)


class TextOutput(StrictModel):
    text: str


class EndDetectOutput(StrictModel):
    complete: bool
    reason: str


class VadOutput(StrictModel):
    voiced: bool
    rms: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)


class TtsOutput(StrictModel):
    audio_url: str
    content_type: Literal["audio/wav"] = "audio/wav"


class TurnResponse(StrictModel):
    transcript: str
    corrected_text: str
    end_detected: bool
    endpoint_reason: str
    response: str
    audio_url: str
    latencies_ms: dict[str, float]


SPEAKER_NOTICE = "Convenience identification only; this is not biometric authentication."


class SpeakerCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=500)


class SpeakerUpdate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=500)


class SpeakerProfile(StrictModel):
    id: str
    name: str
    notes: str
    created_at: datetime
    sample_count: int = Field(ge=0)


class SpeakerEnvelope(StrictModel):
    speaker: SpeakerProfile
    notice: str = SPEAKER_NOTICE


class SpeakerList(StrictModel):
    speakers: list[SpeakerProfile]
    notice: str = SPEAKER_NOTICE


class SpeakerMatch(StrictModel):
    match: SpeakerProfile | None
    score: float | None
    threshold: float


class SpeakerMatchEnvelope(SpeakerMatch):
    notice: str = SPEAKER_NOTICE
