"""PCM framing and frame-level VAD adapters for realtime streams."""

from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
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
        session: Any | None = None,
        model_path: str | Path | None = None,
        sample_rate: int = 16_000,
    ) -> None:
        if model is not None and session is not None:
            raise ValueError("provide either model or ONNX session, not both")
        if sample_rate != 16_000:
            raise ValueError("SileroFrameVAD supports 16 kHz audio only")
        self._model = model if model is not None else (_OnnxSileroModel(session) if session else None)
        self._model_path = Path(model_path) if model_path is not None else None
        self._sample_rate = sample_rate
        self._buffer = np.empty(0, dtype=np.float32)

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        if self._model_path is None:
            raise PlatformError(
                "missing_vad_model",
                "Silero VAD ONNX model path is not configured",
                stage="vad",
            )
        import onnxruntime as ort

        session = ort.InferenceSession(
            str(self._model_path),
            providers=["CPUExecutionProvider"],
        )
        self._model = _OnnxSileroModel(session)

    def score(self, payload: bytes) -> float:
        self._ensure_model()
        incoming = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32_768.0
        self._buffer = np.concatenate((self._buffer, incoming))
        probability = 0.0
        while self._buffer.size >= 512:
            window = self._buffer[:512].copy()
            self._buffer = self._buffer[512:]
            result = self._model(window, self._sample_rate)
            probability = float(result.item() if hasattr(result, "item") else result)
        return probability

    def reset(self) -> None:
        self._buffer = np.empty(0, dtype=np.float32)
        if self._model is not None:
            self._model.reset_states()


class _OnnxSileroModel:
    """Stateful wrapper for the official Silero VAD ONNX input contract."""

    def __init__(self, session: Any) -> None:
        self._session = session
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def __call__(self, samples: np.ndarray, sample_rate: int) -> float:
        probability, state = self._session.run(
            None,
            {
                "input": samples.reshape(1, -1),
                "state": self._state,
                "sr": np.array(sample_rate, dtype=np.int64),
            },
        )
        self._state = state
        return float(np.asarray(probability).squeeze())

    def reset_states(self) -> None:
        self._state.fill(0)
