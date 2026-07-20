"""Strict transport and domain models for realtime speech sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field

from .schemas import StrictModel


class StreamStart(StrictModel):
    type: Literal["stream.start"]
    format: Literal["pcm_s16le"]
    sample_rate: Literal[16_000]
    channels: Literal[1]
    frame_ms: Literal[20, 40]


class StreamStop(StrictModel):
    type: Literal["stream.stop"]


class SessionPing(StrictModel):
    type: Literal["session.ping"]
    nonce: str = Field(min_length=1, max_length=128)


class RealtimeEvent(StrictModel):
    sequence: int = Field(ge=1)
    session_id: str = Field(min_length=1, max_length=128)
    utterance_id: str | None = Field(default=None, max_length=128)
    type: str = Field(min_length=1, max_length=128)
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CorrectionRevision:
    previous_text: str
    current_text: str
    changed: bool


@dataclass(frozen=True, slots=True)
class EndpointDecision:
    complete: bool
    reason: str
