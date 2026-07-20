"""Deterministic VAD-to-utterance endpoint state machine."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4


ActionKind = Literal[
    "speech_started",
    "endpoint_candidate",
    "endpoint_cancelled",
    "utterance_final",
]


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    frame_ms: int
    pre_roll_ms: int
    min_speech_ms: int
    endpoint_ms: int
    hard_endpoint_ms: int
    max_utterance_ms: int

    def __post_init__(self) -> None:
        if self.frame_ms <= 0:
            raise ValueError("frame_ms must be positive")
        if self.pre_roll_ms < 0:
            raise ValueError("pre_roll_ms must not be negative")
        if self.min_speech_ms <= 0:
            raise ValueError("min_speech_ms must be positive")
        if self.endpoint_ms <= 0 or self.endpoint_ms >= self.hard_endpoint_ms:
            raise ValueError("endpoint_ms must be positive and lower than hard_endpoint_ms")
        if self.max_utterance_ms <= 0:
            raise ValueError("max_utterance_ms must be positive")

    @classmethod
    def defaults(cls) -> "DetectorConfig":
        return cls(
            frame_ms=20,
            pre_roll_ms=300,
            min_speech_ms=250,
            endpoint_ms=900,
            hard_endpoint_ms=1_800,
            max_utterance_ms=30_000,
        )


@dataclass(frozen=True, slots=True)
class DetectorAction:
    kind: ActionKind
    utterance_id: str
    pcm: bytes = b""
    silence_ms: int = 0


class UtteranceDetector:
    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        pre_roll_frames = (config.pre_roll_ms + config.frame_ms - 1) // config.frame_ms
        self._pre_roll: deque[bytes] = deque(maxlen=pre_roll_frames)
        self._speech_ms = 0
        self._utterance_id: str | None = None
        self._pcm: list[bytes] = []
        self._duration_ms = 0
        self._silence_ms = 0
        self._candidate = False
        self._extended = False

    def accept(self, frame: bytes, *, voiced: bool) -> list[DetectorAction]:
        if self._utterance_id is None:
            return self._accept_pre_roll(frame, voiced=voiced)

        self._pcm.append(frame)
        self._duration_ms += self.config.frame_ms
        actions: list[DetectorAction] = []

        if voiced:
            self._silence_ms = 0
            if self._candidate:
                self._candidate = False
                self._extended = False
                actions.append(self._action("endpoint_cancelled"))
        else:
            self._silence_ms += self.config.frame_ms
            if not self._candidate and self._silence_ms >= self.config.endpoint_ms:
                self._candidate = True
                actions.append(self._action("endpoint_candidate"))
            if self._candidate and self._silence_ms >= self.config.hard_endpoint_ms:
                actions.append(self._finish())
                return actions

        if self._duration_ms >= self.config.max_utterance_ms:
            actions.append(self._finish())
        return actions

    def _accept_pre_roll(self, frame: bytes, *, voiced: bool) -> list[DetectorAction]:
        self._pre_roll.append(frame)
        if voiced:
            self._speech_ms += self.config.frame_ms
        else:
            self._speech_ms = 0

        if self._speech_ms < self.config.min_speech_ms:
            return []

        self._utterance_id = uuid4().hex
        self._pcm = list(self._pre_roll)
        self._duration_ms = len(self._pcm) * self.config.frame_ms
        self._silence_ms = 0
        self._candidate = False
        self._extended = False
        self._pre_roll.clear()
        actions = [self._action("speech_started")]
        if self._duration_ms >= self.config.max_utterance_ms:
            actions.append(self._finish())
        return actions

    def extend_endpoint(self) -> bool:
        if not self._candidate:
            return False
        self._extended = True
        return True

    def finalize_candidate(self) -> DetectorAction | None:
        if not self._candidate:
            return None
        return self._finish()

    def reset(self) -> None:
        self._pre_roll.clear()
        self._clear_active()

    def _action(self, kind: ActionKind) -> DetectorAction:
        assert self._utterance_id is not None
        return DetectorAction(
            kind=kind,
            utterance_id=self._utterance_id,
            pcm=b"".join(self._pcm),
            silence_ms=self._silence_ms,
        )

    def _finish(self) -> DetectorAction:
        action = self._action("utterance_final")
        self._clear_active()
        return action

    def _clear_active(self) -> None:
        self._speech_ms = 0
        self._utterance_id = None
        self._pcm = []
        self._duration_ms = 0
        self._silence_ms = 0
        self._candidate = False
        self._extended = False
