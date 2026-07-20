"""PCM framing and frame-level VAD adapters for realtime streams."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import io
from typing import Any
import wave

import numpy as np

from .errors import PlatformError


@dataclass(frozen=True, slots=True)
class PCMContract:
    sample_rate: int
    channels: int
    frame_ms: int

    @property
    def frame_bytes(self) -> int:
        return self.sample_rate * self.channels * 2 * self.frame_ms // 1_000

    def validate(self, payload: bytes) -> bytes:
        if len(payload) != self.frame_bytes:
            raise PlatformError(
                "invalid_pcm_frame",
                "PCM frame has an invalid byte length",
                stage="vad",
            )
        return payload


def pcm16_to_wav(payload: bytes, *, sample_rate: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(payload)
    return output.getvalue()


class EnergyFrameVAD:
    def __init__(self, *, threshold: float) -> None:
        self.threshold = threshold

    def score(self, payload: bytes) -> float:
        samples = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32_768.0
        rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
        return min(1.0, rms / self.threshold) if self.threshold else 0.0

    def reset(self) -> None:
        """Energy VAD has no cross-frame model state."""


class SileroFrameVAD:
    """Lazy Silero ONNX adapter with the model's required 512-sample window."""

    def __init__(
        self,
        *,
        model: Any | None = None,
        tensor_factory: Callable[[np.ndarray], Any] | None = None,
        sample_rate: int = 16_000,
    ) -> None:
        self._model = model
        self._tensor_factory = tensor_factory or (lambda samples: samples)
        self._sample_rate = sample_rate
        self._buffer = np.empty(0, dtype=np.float32)

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        import torch
        from silero_vad import load_silero_vad

        self._model = load_silero_vad(onnx=True)
        self._tensor_factory = torch.from_numpy

    def score(self, payload: bytes) -> float:
        self._ensure_model()
        incoming = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32_768.0
        self._buffer = np.concatenate((self._buffer, incoming))
        probability = 0.0
        while self._buffer.size >= 512:
            window = self._buffer[:512].copy()
            self._buffer = self._buffer[512:]
            result = self._model(self._tensor_factory(window), self._sample_rate)
            probability = float(result.item() if hasattr(result, "item") else result)
        return probability

    def reset(self) -> None:
        self._buffer = np.empty(0, dtype=np.float32)
        if self._model is not None:
            self._model.reset_states()
