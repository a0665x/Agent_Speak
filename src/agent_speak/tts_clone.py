"""Bounded VoxCPM2 voice-reference assessment and vLLM-Omni adapter."""

from __future__ import annotations

import base64
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Literal

import httpx
import numpy as np

from .audio import decode_wav
from .errors import PlatformError


ReferenceQuality = Literal[
    "good", "too_quiet", "too_little_voice", "too_short", "too_long"
]


@dataclass(frozen=True, slots=True)
class ReferenceAssessment:
    duration_seconds: float
    rms: float
    peak: float
    voiced_ratio: float
    quality: ReferenceQuality


STYLE_CUES: dict[str, str] = {
    "light_laugh": "speaking with a light laugh",
    "snicker": "with restrained amusement",
    "sigh": "with a soft sighing tone",
    "cough": "with a brief cough-like expression",
    "warm": "warm delivery",
    "cheerful": "cheerful tone",
    "soft": "soft voice",
    "faster": "slightly faster pace",
}


def compile_style_cues(cues: Iterable[str], text: str) -> str:
    """Compile only known UI cues into VoxCPM2 natural-language control text."""
    phrases: list[str] = []
    seen: set[str] = set()
    for cue in cues:
        if cue not in STYLE_CUES:
            raise PlatformError(
                "invalid_style_cue",
                "One or more style cues are not supported",
                stage="tts_clone",
            )
        if cue not in seen:
            phrases.append(STYLE_CUES[cue])
            seen.add(cue)
    if not phrases:
        return text
    return f"({', '.join(phrases)}){text}"


def assess_reference(
    payload: bytes,
    *,
    max_bytes: int,
    rms_threshold: float,
) -> ReferenceAssessment:
    """Assess a transient PCM WAV using deterministic 20 ms energy frames."""
    decoded = decode_wav(
        payload,
        max_bytes=max_bytes,
        max_seconds=60.0,
        stage="tts_clone",
    )
    frame_size = max(1, round(decoded.sample_rate * 0.02))
    frame_rms = [
        float(np.sqrt(np.mean(np.square(frame), dtype=np.float64)))
        for start in range(0, decoded.samples.size, frame_size)
        if (frame := decoded.samples[start : start + frame_size]).size
    ]
    voiced_ratio = (
        sum(value >= rms_threshold for value in frame_rms) / len(frame_rms)
        if frame_rms
        else 0.0
    )

    quality: ReferenceQuality
    if decoded.duration_seconds < 5.0:
        quality = "too_short"
    elif decoded.duration_seconds > 30.0:
        quality = "too_long"
    elif decoded.rms < rms_threshold:
        quality = "too_quiet"
    elif voiced_ratio < 0.5:
        quality = "too_little_voice"
    else:
        quality = "good"

    return ReferenceAssessment(
        duration_seconds=decoded.duration_seconds,
        rms=decoded.rms,
        peak=decoded.peak,
        voiced_ratio=voiced_ratio,
        quality=quality,
    )


class VoxCPMClient:
    """Privacy-bounded client for the private vLLM-Omni speech endpoint."""

    def __init__(
        self,
        base_url: str,
        *,
        request: Callable[[dict[str, object]], bytes] | None = None,
        max_output_bytes: int = 32 * 1024 * 1024,
        max_output_seconds: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_output_bytes = max_output_bytes
        self.max_output_seconds = max_output_seconds
        self._injected_request = request
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=2.0, read=300.0, write=30.0, pool=2.0)
        )

    def synthesize(self, *, text: str, reference_wav: bytes | None) -> bytes:
        payload: dict[str, object] = {
            "model": "voxcpm2",
            "input": text,
            "voice": "default",
            "response_format": "wav",
        }
        if reference_wav is not None:
            encoded = base64.b64encode(reference_wav).decode("ascii")
            payload["ref_audio"] = f"data:audio/wav;base64,{encoded}"

        try:
            result = (
                self._injected_request(payload)
                if self._injected_request is not None
                else self._request(payload)
            )
        except PlatformError:
            raise
        except httpx.TimeoutException as exc:
            raise PlatformError(
                "tts_worker_timeout",
                "Speech generation timed out",
                status_code=504,
                stage="tts_clone",
                retryable=True,
            ) from exc
        except httpx.ConnectError as exc:
            raise PlatformError(
                "tts_worker_unavailable",
                "Speech generation worker is unavailable",
                status_code=503,
                stage="tts_clone",
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            if self._is_out_of_memory(exc):
                raise PlatformError(
                    "gpu_out_of_memory",
                    "The GPU does not have enough free memory for speech generation",
                    status_code=503,
                    stage="tts_clone",
                    retryable=True,
                ) from exc
            raise PlatformError(
                "tts_worker_error",
                "Speech generation worker rejected the request",
                status_code=502,
                stage="tts_clone",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise PlatformError(
                "tts_worker_unavailable",
                "Speech generation worker is unavailable",
                status_code=503,
                stage="tts_clone",
                retryable=True,
            ) from exc

        if len(result) > self.max_output_bytes:
            raise PlatformError(
                "tts_output_too_large",
                "Generated audio exceeds the configured byte limit",
                status_code=502,
                stage="tts_clone",
            )
        try:
            decoded = decode_wav(
                result,
                max_bytes=self.max_output_bytes,
                max_seconds=self.max_output_seconds,
                stage="tts_clone",
            )
        except PlatformError as exc:
            raise PlatformError(
                "invalid_tts_audio",
                "Speech generation worker returned invalid audio",
                status_code=502,
                stage="tts_clone",
                retryable=True,
            ) from exc
        if decoded.sample_rate != 48_000:
            raise PlatformError(
                "invalid_tts_audio",
                "Speech generation worker returned an unsupported sample rate",
                status_code=502,
                stage="tts_clone",
                retryable=True,
            )
        return result

    def is_ready(self) -> bool:
        if self._injected_request is not None:
            return True
        try:
            response = self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _request(self, payload: dict[str, object]) -> bytes:
        chunks = bytearray()
        with self._client.stream(
            "POST",
            f"{self.base_url}/v1/audio/speech",
            json=payload,
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                chunks.extend(chunk)
                if len(chunks) > self.max_output_bytes:
                    raise PlatformError(
                        "tts_output_too_large",
                        "Generated audio exceeds the configured byte limit",
                        status_code=502,
                        stage="tts_clone",
                    )
        return bytes(chunks)

    @staticmethod
    def _is_out_of_memory(exc: httpx.HTTPStatusError) -> bool:
        details = str(exc).lower()
        try:
            details += " " + exc.response.text.lower()
        except (httpx.ResponseNotRead, UnicodeDecodeError):
            pass
        return "out of memory" in details or "cuda oom" in details
