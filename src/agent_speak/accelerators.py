"""Deterministic in-container accelerator selection for speech providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from .errors import PlatformError


AcceleratorMode = Literal["auto", "cpu", "nvidia"]


@dataclass(frozen=True, slots=True)
class ASRDeviceSelection:
    device: Literal["cpu", "cuda"]
    compute_type: str
    fallback_reason: str | None


def ctranslate2_cuda_available() -> bool:
    """Return whether CTranslate2 can initialize at least one CUDA device."""

    import ctranslate2

    if ctranslate2.get_cuda_device_count() < 1:
        return False
    return bool(ctranslate2.get_supported_compute_types("cuda"))


def select_asr_device(
    mode: AcceleratorMode,
    cpu_compute_type: str,
    cuda_compute_type: str,
    cuda_probe: Callable[[], bool] = ctranslate2_cuda_available,
) -> ASRDeviceSelection:
    """Select one ASR device without exposing raw probe errors to clients."""

    if mode == "cpu":
        return ASRDeviceSelection("cpu", cpu_compute_type, None)
    try:
        available = cuda_probe()
    except Exception as exc:
        if mode == "nvidia":
            raise PlatformError(
                "provider_unavailable",
                "NVIDIA acceleration was required but the CUDA probe failed",
                status_code=503,
                stage="asr",
                retryable=False,
            ) from exc
        return ASRDeviceSelection("cpu", cpu_compute_type, "CUDA probe failed")
    if available:
        return ASRDeviceSelection("cuda", cuda_compute_type, None)
    if mode == "nvidia":
        raise PlatformError(
            "provider_unavailable",
            "NVIDIA acceleration was required but CUDA is unavailable",
            status_code=503,
            stage="asr",
            retryable=False,
        )
    return ASRDeviceSelection("cpu", cpu_compute_type, "CUDA is unavailable inside the container")
