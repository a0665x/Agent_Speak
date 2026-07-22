"""Gateway-side model catalog and bounded ASR worker control client."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from .errors import PlatformError
from .model_ids import ASRModelId, CorrectionModelId, DEFAULT_CORRECTION_MODEL
from .schemas import (
    ASRModelOption,
    ActiveModelSelection,
    CorrectionModelOption,
    ModelCatalog,
)


MAX_CONTROL_RESPONSE_BYTES = 64 * 1024


class WorkerModelControl(Protocol):
    def snapshot(self) -> dict[str, object]: ...

    def activate(self, model_id: ASRModelId) -> dict[str, object]: ...

    def acquire(self, session_id: str, model_id: ASRModelId) -> dict[str, object]: ...

    def release(self, session_id: str) -> dict[str, object]: ...


class ASRWorkerControlClient:
    def __init__(
        self,
        base_url: str,
        *,
        request: Callable[[str, str, dict[str, object] | None], tuple[int, dict[str, object]]] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._injected_request = request
        self._client = httpx.Client(timeout=httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0))

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        if self._injected_request is not None:
            status_code, body = self._injected_request(method, path, payload)
        else:
            try:
                response = self._client.request(
                    method,
                    f"{self.base_url}{path}",
                    json=payload,
                )
                if len(response.content) > MAX_CONTROL_RESPONSE_BYTES:
                    raise ValueError("response too large")
                body = response.json()
                status_code = response.status_code
            except (httpx.HTTPError, ValueError) as exc:
                raise self._unavailable() from exc
        if not isinstance(body, dict):
            raise self._unavailable()
        if status_code >= 400:
            error = body.get("error")
            if not isinstance(error, dict):
                raise self._unavailable()
            code = error.get("code")
            message = error.get("message")
            stage = error.get("stage")
            retryable = error.get("retryable", False)
            if not isinstance(code, str) or not isinstance(message, str) or not isinstance(retryable, bool):
                raise self._unavailable()
            raise PlatformError(
                code,
                message,
                status_code=status_code,
                stage=stage if isinstance(stage, str) else None,
                retryable=retryable,
            )
        return body

    @staticmethod
    def _unavailable() -> PlatformError:
        return PlatformError(
            "asr_worker_unavailable",
            "ASR worker control request failed",
            status_code=503,
            stage="asr",
            retryable=True,
        )

    def snapshot(self) -> dict[str, object]:
        return self._request("GET", "/internal/v1/models")

    def activate(self, model_id: ASRModelId) -> dict[str, object]:
        return self._request("PUT", "/internal/v1/models/active", {"asr_model": model_id})

    def acquire(self, session_id: str, model_id: ASRModelId) -> dict[str, object]:
        safe_session = quote(session_id, safe="")
        return self._request(
            "POST",
            f"/internal/v1/models/lease/{safe_session}?asr_model={model_id}",
        )

    def release(self, session_id: str) -> dict[str, object]:
        safe_session = quote(session_id, safe="")
        return self._request("DELETE", f"/internal/v1/models/lease/{safe_session}")


class UnavailableWorkerModelControl:
    def snapshot(self) -> dict[str, object]:
        return {
            "state": "unavailable",
            "active_asr_model": None,
            "requested_asr_model": None,
            "leased_by": None,
            "device": "unavailable",
            "error_code": "asr_worker_unavailable",
        }

    def activate(self, model_id: ASRModelId) -> dict[str, object]:
        del model_id
        raise ASRWorkerControlClient._unavailable()

    def acquire(self, session_id: str, model_id: ASRModelId) -> dict[str, object]:
        del session_id, model_id
        raise ASRWorkerControlClient._unavailable()

    def release(self, session_id: str) -> dict[str, object]:
        del session_id
        return self.snapshot()


ASR_OPTIONS: tuple[tuple[ASRModelId, str, str], ...] = (
    ("qwen3-asr-1.7b", "Qwen3-ASR 1.7B", "Multilingual recognition for mixed and noisy speech."),
    ("breeze-asr-25", "Breeze ASR 25", "Taiwan Mandarin and Mandarin-English code-switching."),
    ("faster-whisper-small", "Faster-Whisper Small", "Compact compatibility model."),
)


class ModelCatalogService:
    def __init__(
        self,
        *,
        worker: WorkerModelControl,
        correction_ready: Callable[[], bool],
        correction_model: CorrectionModelId = DEFAULT_CORRECTION_MODEL,
    ) -> None:
        self.worker = worker
        self._correction_ready = correction_ready
        self._correction_model = correction_model
        self._lock = Lock()

    def _catalog(self, snapshot: dict[str, object]) -> ModelCatalog:
        state = snapshot.get("state")
        active_asr = snapshot.get("active_asr_model")
        requested = snapshot.get("requested_asr_model")
        leased_by = snapshot.get("leased_by")
        device = snapshot.get("device")
        error_code = snapshot.get("error_code")
        if state not in {"unavailable", "idle", "unloading", "loading", "warming", "ready", "failed", "rollback"}:
            raise ASRWorkerControlClient._unavailable()
        known_asr = {item[0] for item in ASR_OPTIONS}
        if active_asr is not None and active_asr not in known_asr:
            raise ASRWorkerControlClient._unavailable()
        if requested is not None and requested not in known_asr:
            raise ASRWorkerControlClient._unavailable()
        worker_available = state != "unavailable"
        asr_options = [
            ASRModelOption(id=model_id, label=label, description=description, ready=worker_available)
            for model_id, label, description in ASR_OPTIONS
        ]
        correction_available = bool(self._correction_ready())
        correction_options = [
            CorrectionModelOption(
                id="qwen2.5-correction",
                label="Qwen2.5 Correction",
                description="Local punctuation and recognition-text correction.",
                ready=correction_available,
            ),
            CorrectionModelOption(
                id="disabled",
                label="Disabled / Raw ASR",
                description="Keep the final ASR text without correction.",
                ready=True,
            ),
        ]
        return ModelCatalog(
            asr=asr_options,
            correction=correction_options,
            active=ActiveModelSelection(
                asr_model=active_asr,
                correction_model=self._correction_model,
                requested_asr_model=requested,
                state=state,
                leased_by=leased_by if isinstance(leased_by, str) else None,
                device=device if isinstance(device, str) else "unavailable",
                error_code=error_code if isinstance(error_code, str) else None,
            ),
        )

    def catalog(self) -> ModelCatalog:
        with self._lock:
            return self._catalog(self.worker.snapshot())

    def activate(self, asr_model: ASRModelId, correction_model: CorrectionModelId) -> ModelCatalog:
        with self._lock:
            if correction_model == "qwen2.5-correction" and not self._correction_ready():
                raise PlatformError(
                    "model_not_ready",
                    "The correction model is not ready",
                    status_code=409,
                    stage="correction",
                    retryable=True,
                )
            snapshot = self.worker.activate(asr_model)
            self._correction_model = correction_model
            return self._catalog(snapshot)
