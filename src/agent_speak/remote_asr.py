"""Provider-compatible client for the internal ASR worker."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

import httpx

from .errors import PlatformError


class RemoteASRProvider:
    def __init__(
        self,
        base_url: str,
        *,
        request: Callable[[dict[str, object]], dict[str, object]] | None = None,
        max_audio_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_audio_bytes = max_audio_bytes
        self.device = "unavailable"
        self.fallback_reason: str | None = None
        self._injected_request = request
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=2.0, read=30.0, write=10.0, pool=2.0)
        )

    def transcribe(self, audio: bytes) -> str:
        return self.transcribe_mode(audio, "final")

    def transcribe_mode(self, audio: bytes, mode: Literal["partial", "final"] | str) -> str:
        if mode not in {"partial", "final"}:
            raise ValueError("mode must be partial or final")
        if len(audio) > self.max_audio_bytes:
            raise PlatformError(
                "audio_too_large",
                "Audio exceeds the configured byte limit",
                status_code=413,
                stage="asr",
            )
        payload: dict[str, object] = {"audio": audio, "mode": mode}
        if self._injected_request is not None:
            result = self._injected_request(payload)
        else:
            try:
                response = self._client.post(
                    f"{self.base_url}/internal/v1/asr",
                    params={"mode": mode},
                    content=audio,
                    headers={"content-type": "audio/wav"},
                )
                response.raise_for_status()
                result = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise PlatformError(
                    "asr_worker_unavailable",
                    "ASR worker request failed",
                    status_code=503,
                    stage="asr",
                    retryable=True,
                ) from exc
        if not isinstance(result, dict):
            self._raise_invalid()
        text = result.get("text")
        device = result.get("device")
        if not isinstance(text, str) or not text.strip() or not isinstance(device, str):
            self._raise_invalid()
        self.device = device
        return text.strip()

    def is_ready(self) -> bool:
        if self._injected_request is not None:
            return True
        try:
            response = self._client.get(f"{self.base_url}/internal/v1/health")
            payload = response.json()
            ready = response.status_code == 200 and payload.get("ready") is True
            if ready and isinstance(payload.get("device"), str):
                self.device = payload["device"]
            return ready
        except (httpx.HTTPError, ValueError, AttributeError):
            return False

    @staticmethod
    def _raise_invalid() -> None:
        raise PlatformError(
            "invalid_asr_worker_response",
            "ASR worker returned invalid JSON",
            status_code=502,
            stage="asr",
            retryable=True,
        )
