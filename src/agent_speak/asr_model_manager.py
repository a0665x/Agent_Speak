"""Single-resident ASR provider lifecycle and lease management."""

from __future__ import annotations

import gc
from dataclasses import dataclass, replace
from threading import Lock
from typing import Callable, Literal, Mapping

from .asr_providers import ASRProvider
from .errors import PlatformError
from .model_ids import ASRModelId


ModelLoadState = Literal[
    "unavailable",
    "idle",
    "unloading",
    "loading",
    "warming",
    "ready",
    "failed",
    "rollback",
]


@dataclass(frozen=True, slots=True)
class ModelManagerSnapshot:
    state: ModelLoadState
    active_asr_model: ASRModelId | None
    requested_asr_model: ASRModelId | None
    leased_by: str | None
    device: str
    error_code: str | None


class ModelLeaseConflict(PlatformError):
    def __init__(self, message: str = "The active ASR model is in use by another session") -> None:
        super().__init__(
            "model_in_use",
            message,
            status_code=409,
            stage="asr",
            retryable=True,
        )


def release_inference_memory() -> None:
    """Release Python objects and an available CUDA allocator cache."""

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except (ImportError, RuntimeError):
        return


class ASRModelManager:
    """Own exactly one warmed provider and an optional realtime lease.

    State is published as immutable snapshots. ``snapshot`` is intentionally
    lock-free so an API poll can observe progress while a slow ``warm`` call is
    protected by the manager's lifecycle lock.
    """

    def __init__(
        self,
        *,
        factories: Mapping[ASRModelId, Callable[[], ASRProvider]],
        device: str,
        memory_cleanup: Callable[[], None] = release_inference_memory,
    ) -> None:
        self.factories = dict(factories)
        self._configured_device = device
        self._memory_cleanup = memory_cleanup
        self._provider: ASRProvider | None = None
        self._active_model: ASRModelId | None = None
        self._lock = Lock()
        self._snapshot = ModelManagerSnapshot(
            state="idle",
            active_asr_model=None,
            requested_asr_model=None,
            leased_by=None,
            device=device,
            error_code=None,
        )

    def snapshot(self) -> ModelManagerSnapshot:
        return self._snapshot

    def _publish(
        self,
        *,
        state: ModelLoadState,
        active: ASRModelId | None,
        requested: ASRModelId | None,
        error_code: str | None,
        leased_by: str | None = None,
        device: str | None = None,
    ) -> ModelManagerSnapshot:
        self._snapshot = ModelManagerSnapshot(
            state=state,
            active_asr_model=active,
            requested_asr_model=requested,
            leased_by=self._snapshot.leased_by if leased_by is None else leased_by,
            device=device or self._configured_device,
            error_code=error_code,
        )
        return self._snapshot

    def _validate_model(self, model_id: ASRModelId) -> None:
        if model_id not in self.factories:
            raise PlatformError(
                "unknown_asr_model",
                "The requested ASR model is not supported",
                status_code=422,
                stage="asr",
                retryable=False,
            )

    @staticmethod
    def _activation_error() -> PlatformError:
        return PlatformError(
            "model_activation_failed",
            "The requested ASR model could not be activated",
            status_code=503,
            stage="asr",
            retryable=True,
        )

    @staticmethod
    def _rollback_error() -> PlatformError:
        return PlatformError(
            "model_rollback_failed",
            "ASR model activation and rollback both failed",
            status_code=503,
            stage="asr",
            retryable=False,
        )

    def activate(self, model_id: ASRModelId) -> ModelManagerSnapshot:
        self._validate_model(model_id)
        with self._lock:
            if self._snapshot.leased_by is not None and model_id != self._active_model:
                raise ModelLeaseConflict()
            if self._provider is not None and self._active_model == model_id and self._snapshot.state == "ready":
                return self._snapshot

            previous_model = self._active_model
            previous_provider = self._provider
            candidate: ASRProvider | None = None
            try:
                if previous_provider is not None:
                    self._publish(
                        state="unloading",
                        active=previous_model,
                        requested=model_id,
                        error_code=None,
                    )
                    self._provider = None
                    self._active_model = None
                    previous_provider.close()
                    self._memory_cleanup()

                self._publish(state="loading", active=None, requested=model_id, error_code=None)
                candidate = self.factories[model_id]()
                self._publish(
                    state="warming",
                    active=None,
                    requested=model_id,
                    error_code=None,
                    device=candidate.device,
                )
                candidate.warm()
                self._provider = candidate
                self._active_model = model_id
                return self._publish(
                    state="ready",
                    active=model_id,
                    requested=None,
                    error_code=None,
                    device=candidate.device,
                )
            except Exception as activation_cause:
                if candidate is not None:
                    try:
                        candidate.close()
                    except Exception:
                        pass
                    self._memory_cleanup()
                activation_error = self._activation_error()
                if previous_model is None:
                    self._provider = None
                    self._active_model = None
                    self._publish(
                        state="failed",
                        active=None,
                        requested=None,
                        error_code=activation_error.code,
                    )
                    raise activation_error from activation_cause

                self._publish(
                    state="rollback",
                    active=None,
                    requested=model_id,
                    error_code=activation_error.code,
                )
                rollback_provider: ASRProvider | None = None
                try:
                    rollback_provider = self.factories[previous_model]()
                    rollback_provider.warm()
                    self._provider = rollback_provider
                    self._active_model = previous_model
                    self._publish(
                        state="ready",
                        active=previous_model,
                        requested=None,
                        error_code=activation_error.code,
                        device=rollback_provider.device,
                    )
                    raise activation_error from activation_cause
                except PlatformError as exc:
                    if exc is activation_error:
                        raise
                    rollback_cause: Exception = exc
                except Exception as exc:
                    rollback_cause = exc

                if rollback_provider is not None:
                    try:
                        rollback_provider.close()
                    except Exception:
                        pass
                    self._memory_cleanup()
                rollback_error = self._rollback_error()
                self._provider = None
                self._active_model = None
                self._publish(
                    state="failed",
                    active=None,
                    requested=None,
                    error_code=rollback_error.code,
                )
                raise rollback_error from rollback_cause

    def acquire(self, session_id: str, model_id: ASRModelId) -> ModelManagerSnapshot:
        self._validate_model(model_id)
        with self._lock:
            if self._snapshot.leased_by not in (None, session_id):
                raise ModelLeaseConflict()
            if self._provider is None or self._active_model != model_id or self._snapshot.state != "ready":
                raise PlatformError(
                    "model_not_ready",
                    "The session ASR model is not active",
                    status_code=409,
                    stage="asr",
                    retryable=True,
                )
            self._snapshot = replace(self._snapshot, leased_by=session_id)
            return self._snapshot

    def release(self, session_id: str) -> ModelManagerSnapshot:
        with self._lock:
            if self._snapshot.leased_by == session_id:
                self._snapshot = replace(self._snapshot, leased_by=None)
            return self._snapshot

    def transcribe(
        self,
        session_id: str | None,
        model_id: ASRModelId,
        audio: bytes,
        *,
        language: str | None = None,
    ) -> str:
        self._validate_model(model_id)
        with self._lock:
            lease_owner = self._snapshot.leased_by
            if lease_owner is not None and lease_owner != session_id:
                raise ModelLeaseConflict()
            if session_id is not None and lease_owner != session_id:
                raise ModelLeaseConflict("The realtime session does not own the active ASR lease")
            if self._provider is None or self._active_model != model_id or self._snapshot.state != "ready":
                raise PlatformError(
                    "model_not_ready",
                    "The requested ASR model is not ready",
                    status_code=409,
                    stage="asr",
                    retryable=True,
                )
            return self._provider.transcribe(audio, language=language)
