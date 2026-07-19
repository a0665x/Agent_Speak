"""Local production ASR and TTS providers.

Heavy models are loaded lazily on first use so startup and health checks stay fast.
"""

from __future__ import annotations

import io
from pathlib import Path
from threading import Lock
from typing import Any, Callable
import wave

from .errors import PlatformError


class FasterWhisperASR:
    def __init__(
        self,
        *,
        model_name: str = "small",
        language: str | None = "zh",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_name = model_name
        self.language = language
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self._model_factory = model_factory
        self._local_model_resolver: Callable[[str], Path] = self._resolve_local_model
        self._model: Any | None = None
        self._lock = Lock()

    @staticmethod
    def _resolve_local_model(model_name: str) -> Path:
        configured_path = Path(model_name).expanduser()
        if configured_path.is_dir():
            return configured_path
        from faster_whisper.utils import download_model

        return Path(download_model(model_name, local_files_only=True))

    def is_ready(self) -> bool:
        if self._model is not None:
            return True
        try:
            model_path = self._local_model_resolver(self.model_name)
        except Exception:
            return False
        required_files = ("model.bin", "config.json", "tokenizer.json")
        return model_path.is_dir() and all((model_path / name).is_file() for name in required_files)

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                try:
                    factory = self._model_factory
                    if factory is None:
                        from faster_whisper import WhisperModel

                        factory = WhisperModel
                    self._model = factory(
                        self.model_name,
                        device="cpu",
                        compute_type=self.compute_type,
                        cpu_threads=self.cpu_threads,
                        num_workers=1,
                    )
                except Exception as exc:
                    raise PlatformError(
                        "provider_unavailable",
                        "Faster-Whisper ASR model could not be loaded",
                        status_code=503,
                        stage="asr",
                        retryable=True,
                    ) from exc
        return self._model

    def transcribe(self, audio: bytes) -> str:
        try:
            segments, _ = self._load_model().transcribe(
                io.BytesIO(audio),
                language=self.language,
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            text = "".join(segment.text for segment in segments).strip()
        except PlatformError:
            raise
        except Exception as exc:
            raise PlatformError(
                "asr_failed",
                "Faster-Whisper could not transcribe the audio",
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


class PiperTTS:
    def __init__(
        self,
        *,
        model_path: Path,
        voice_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.config_path = Path(f"{self.model_path}.json")
        self._voice_factory = voice_factory
        self._voice: Any | None = None
        self._lock = Lock()

    def _load_voice(self) -> Any:
        if self._voice is not None:
            return self._voice
        with self._lock:
            if self._voice is None:
                if not self.model_path.is_file() or not self.config_path.is_file():
                    raise PlatformError(
                        "provider_unavailable",
                        f"Piper voice model is missing: {self.model_path}",
                        status_code=503,
                        stage="tts",
                        retryable=False,
                    )
                try:
                    factory = self._voice_factory
                    if factory is None:
                        from piper import PiperVoice

                        factory = PiperVoice.load
                    self._voice = factory(self.model_path, config_path=self.config_path, use_cuda=False)
                except Exception as exc:
                    raise PlatformError(
                        "provider_unavailable",
                        "Piper TTS voice could not be loaded",
                        status_code=503,
                        stage="tts",
                        retryable=True,
                    ) from exc
        return self._voice

    def synthesize(self, text: str) -> bytes:
        output = io.BytesIO()
        try:
            with wave.open(output, "wb") as wav_file:
                self._load_voice().synthesize_wav(text, wav_file)
        except PlatformError:
            raise
        except Exception as exc:
            raise PlatformError(
                "tts_failed",
                "Piper could not synthesize the response",
                status_code=500,
                stage="tts",
                retryable=True,
            ) from exc
        payload = output.getvalue()
        if len(payload) <= 44:
            raise PlatformError("tts_failed", "Piper returned empty audio", status_code=500, stage="tts", retryable=True)
        return payload
