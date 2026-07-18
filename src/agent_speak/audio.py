"""Bounded WAV decoding and a functional energy voice activity detector."""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import numpy as np

from .errors import PlatformError


@dataclass(frozen=True, slots=True)
class DecodedAudio:
    sample_rate: int
    channels: int
    samples: np.ndarray
    duration_seconds: float
    rms: float
    peak: float


def decode_wav(payload: bytes, *, max_bytes: int, max_seconds: float, stage: str = "vad") -> DecodedAudio:
    if len(payload) > max_bytes:
        raise PlatformError("audio_too_large", "Audio exceeds the configured byte limit", status_code=413, stage=stage)
    if len(payload) < 44:
        raise PlatformError("invalid_wav", "Audio must be a PCM WAV file", stage=stage)
    try:
        with wave.open(io.BytesIO(payload), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frame_count = wav.getnframes()
            compression = wav.getcomptype()
            if channels not in (1, 2) or sample_width != 2 or compression != "NONE":
                raise PlatformError(
                    "unsupported_wav",
                    "WAV must be uncompressed 16-bit mono or stereo PCM",
                    status_code=415,
                    stage=stage,
                )
            if not 8_000 <= sample_rate <= 48_000:
                raise PlatformError("unsupported_sample_rate", "WAV sample rate must be 8–48 kHz", status_code=415, stage=stage)
            duration = frame_count / sample_rate
            if duration > max_seconds:
                raise PlatformError("audio_too_long", "Audio exceeds the configured duration limit", status_code=413, stage=stage)
            raw = wav.readframes(frame_count)
    except PlatformError:
        raise
    except (EOFError, wave.Error, ValueError) as exc:
        raise PlatformError("invalid_wav", "Audio must be a PCM WAV file", stage=stage) from exc
    expected = frame_count * channels * sample_width
    if len(raw) != expected:
        raise PlatformError("invalid_wav", "WAV frame data is truncated", stage=stage)
    pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32_768.0
    if channels == 2:
        pcm = pcm.reshape(-1, 2).mean(axis=1, dtype=np.float32)
    peak = float(np.max(np.abs(pcm))) if pcm.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(pcm), dtype=np.float64))) if pcm.size else 0.0
    return DecodedAudio(sample_rate, channels, pcm, duration, rms, peak)


class EnergyVAD:
    def __init__(self, *, max_bytes: int, max_seconds: float, rms_threshold: float) -> None:
        self.max_bytes = max_bytes
        self.max_seconds = max_seconds
        self.rms_threshold = rms_threshold

    def detect(self, audio: bytes) -> dict[str, object]:
        decoded = decode_wav(audio, max_bytes=self.max_bytes, max_seconds=self.max_seconds)
        return {
            "voiced": decoded.rms >= self.rms_threshold,
            "rms": round(decoded.rms, 6),
            "duration_seconds": round(decoded.duration_seconds, 6),
        }
