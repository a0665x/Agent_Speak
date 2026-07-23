"""Bounded local adapters for the selectable speech-recognition models.

Heavy inference libraries and weights are intentionally loaded only by ``warm``
or ``transcribe``. Runtime loading is local-only so a request can never trigger
an implicit model download.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Callable, Protocol

import numpy as np

from .accelerators import AcceleratorMode
from .audio import decode_wav
from .errors import PlatformError


DEFAULT_MAX_AUDIO_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_AUDIO_SECONDS = 30.0
TARGET_SAMPLE_RATE = 16_000


class ASRProvider(Protocol):
    device: str

    def warm(self) -> None: ...

    def close(self) -> None: ...

    def transcribe(self, audio: bytes, language: str | None = None) -> str: ...


def _torch_cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _select_device(accelerator: AcceleratorMode, cuda_probe: Callable[[], bool]) -> str:
    if accelerator == "cpu":
        return "cpu"
    try:
        available = cuda_probe()
    except Exception as exc:
        if accelerator == "nvidia":
            raise PlatformError(
                "provider_unavailable",
                "NVIDIA acceleration was required but the CUDA probe failed",
                status_code=503,
                stage="asr",
                retryable=False,
            ) from exc
        return "cpu"
    if available:
        return "cuda"
    if accelerator == "nvidia":
        raise PlatformError(
            "provider_unavailable",
            "NVIDIA acceleration was required but CUDA is unavailable",
            status_code=503,
            stage="asr",
            retryable=False,
        )
    return "cpu"


def resample_mono(samples: np.ndarray, source_rate: int, target_rate: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Linearly resample mono float audio without another runtime dependency."""

    source = np.asarray(samples, dtype=np.float32)
    if source_rate == target_rate or source.size == 0:
        return source.copy()
    output_size = max(1, round(source.size * target_rate / source_rate))
    source_positions = np.arange(source.size, dtype=np.float64)
    target_positions = np.arange(output_size, dtype=np.float64) * source_rate / target_rate
    target_positions = np.minimum(target_positions, source.size - 1)
    return np.interp(target_positions, source_positions, source).astype(np.float32)


def _decode_16k(audio: bytes, *, max_bytes: int, max_seconds: float) -> np.ndarray:
    decoded = decode_wav(audio, max_bytes=max_bytes, max_seconds=max_seconds, stage="asr")
    return resample_mono(decoded.samples, decoded.sample_rate)


def _move_inputs_to_device(inputs: Any, device: str, *, floating_dtype: Any | None = None) -> dict[str, Any]:
    values = dict(inputs)
    if device == "cuda":
        moved: dict[str, Any] = {}
        for key, value in values.items():
            if not hasattr(value, "to"):
                moved[key] = value
                continue
            is_floating = getattr(value, "is_floating_point", lambda: False)()
            moved[key] = value.to(device, dtype=floating_dtype) if is_floating and floating_dtype is not None else value.to(device)
        values = moved
    return values


def _default_breeze_processor_factory(*, model_path: Path, device: str) -> Any:
    del device
    if not model_path.is_dir():
        raise FileNotFoundError("Breeze ASR model directory is unavailable")
    from transformers import AutoProcessor

    return AutoProcessor.from_pretrained(str(model_path), local_files_only=True)


def _default_breeze_model_factory(*, model_path: Path, device: str) -> Any:
    if not model_path.is_dir():
        raise FileNotFoundError("Breeze ASR model directory is unavailable")
    import torch
    from transformers import AutoModelForSpeechSeq2Seq

    dtype = torch.float16 if device == "cuda" else torch.float32
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        str(model_path),
        local_files_only=True,
        torch_dtype=dtype,
    )
    return model.to(device)


class BreezeASR:
    """Transformers adapter for MediaTek Research Breeze ASR 25."""

    def __init__(
        self,
        *,
        model_path: Path,
        accelerator: AcceleratorMode = "auto",
        max_audio_bytes: int = DEFAULT_MAX_AUDIO_BYTES,
        max_audio_seconds: float = DEFAULT_MAX_AUDIO_SECONDS,
        cuda_probe: Callable[[], bool] | None = None,
        processor_factory: Callable[..., Any] | None = None,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.device = _select_device(accelerator, cuda_probe or _torch_cuda_available)
        self.max_audio_bytes = max_audio_bytes
        self.max_audio_seconds = max_audio_seconds
        self._processor_factory = processor_factory or _default_breeze_processor_factory
        self._model_factory = model_factory or _default_breeze_model_factory
        self._processor: Any | None = None
        self._model: Any | None = None
        self._lock = Lock()

    def _load_runtime(self) -> tuple[Any, Any]:
        if self._processor is not None and self._model is not None:
            return self._processor, self._model
        with self._lock:
            if self._processor is None or self._model is None:
                try:
                    processor = self._processor_factory(model_path=self.model_path, device=self.device)
                    model = self._model_factory(model_path=self.model_path, device=self.device)
                except Exception as exc:
                    raise PlatformError(
                        "provider_unavailable",
                        "Breeze ASR model could not be loaded",
                        status_code=503,
                        stage="asr",
                        retryable=True,
                    ) from exc
                self._processor = processor
                self._model = model
        return self._processor, self._model

    def warm(self) -> None:
        self._load_runtime()

    def close(self) -> None:
        with self._lock:
            self._model = None
            self._processor = None

    def transcribe(self, audio: bytes, language: str | None = None) -> str:
        samples = _decode_16k(audio, max_bytes=self.max_audio_bytes, max_seconds=self.max_audio_seconds)
        processor, model = self._load_runtime()
        try:
            inputs = processor(samples, sampling_rate=TARGET_SAMPLE_RATE, return_tensors="pt")
            generate_kwargs = _move_inputs_to_device(inputs, self.device, floating_dtype=getattr(model, "dtype", None))
            if language not in (None, "auto"):
                generate_kwargs["language"] = language
            generated = model.generate(**generate_kwargs)
            decoded = processor.batch_decode(generated, skip_special_tokens=True)
            text = str(decoded[0]).strip() if decoded else ""
        except PlatformError:
            raise
        except Exception as exc:
            raise PlatformError(
                "asr_failed",
                "Breeze ASR could not transcribe the audio",
                status_code=500,
                stage="asr",
                retryable=True,
            ) from exc
        if not text:
            raise PlatformError(
                "no_transcript",
                "Speech was detected but no words could be recognized",
                status_code=422,
                stage="asr",
                retryable=True,
            )
        return text


QWEN_LANGUAGE_NAMES: dict[str, str] = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
}


def _default_qwen_model_factory(*, model_path: Path, device: str) -> Any:
    if not model_path.is_dir():
        raise FileNotFoundError("Qwen3-ASR model directory is unavailable")
    import torch
    from qwen_asr import Qwen3ASRModel

    dtype = torch.float16 if device == "cuda" else torch.float32
    return Qwen3ASRModel.from_pretrained(
        str(model_path),
        dtype=dtype,
        device_map="cuda:0" if device == "cuda" else "cpu",
        local_files_only=True,
        max_inference_batch_size=1,
        max_new_tokens=256,
    )


class Qwen3ASR:
    """Adapter for Qwen3-ASR using its native array input API."""

    def __init__(
        self,
        *,
        model_path: Path,
        accelerator: AcceleratorMode = "auto",
        max_audio_bytes: int = DEFAULT_MAX_AUDIO_BYTES,
        max_audio_seconds: float = DEFAULT_MAX_AUDIO_SECONDS,
        cuda_probe: Callable[[], bool] | None = None,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.device = _select_device(accelerator, cuda_probe or _torch_cuda_available)
        self.max_audio_bytes = max_audio_bytes
        self.max_audio_seconds = max_audio_seconds
        self._model_factory = model_factory or _default_qwen_model_factory
        self._model: Any | None = None
        self._lock = Lock()

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                try:
                    self._model = self._model_factory(model_path=self.model_path, device=self.device)
                except Exception as exc:
                    raise PlatformError(
                        "provider_unavailable",
                        "Qwen3-ASR model could not be loaded",
                        status_code=503,
                        stage="asr",
                        retryable=True,
                    ) from exc
        return self._model

    def warm(self) -> None:
        self._load_model()

    def close(self) -> None:
        with self._lock:
            self._model = None

    def transcribe(self, audio: bytes, language: str | None = None) -> str:
        samples = _decode_16k(audio, max_bytes=self.max_audio_bytes, max_seconds=self.max_audio_seconds)
        requested_language = QWEN_LANGUAGE_NAMES.get(language or "")
        try:
            results = self._load_model().transcribe(
                audio=(samples, TARGET_SAMPLE_RATE),
                language=requested_language,
            )
            first = results[0] if results else None
            if isinstance(first, dict):
                text = str(first.get("text", "")).strip()
            else:
                text = str(getattr(first, "text", "")).strip()
        except PlatformError:
            raise
        except Exception as exc:
            raise PlatformError(
                "asr_failed",
                "Qwen3-ASR could not transcribe the audio",
                status_code=500,
                stage="asr",
                retryable=True,
            ) from exc
        if not text:
            raise PlatformError(
                "no_transcript",
                "Speech was detected but no words could be recognized",
                status_code=422,
                stage="asr",
                retryable=True,
            )
        return text
