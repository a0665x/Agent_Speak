from __future__ import annotations

from typing import Any

import pytest

from agent_speak.errors import PlatformError
from agent_speak.model_control import ASRWorkerControlClient, ModelCatalogService


READY_SNAPSHOT = {
    "state": "ready",
    "active_asr_model": "qwen3-asr-1.7b",
    "requested_asr_model": None,
    "leased_by": None,
    "device": "cuda",
    "error_code": None,
}


class FakeWorkerClient:
    def __init__(self) -> None:
        self.current = dict(READY_SNAPSHOT)
        self.activations: list[str] = []

    def snapshot(self) -> dict[str, object]:
        return dict(self.current)

    def activate(self, model_id: str) -> dict[str, object]:
        self.activations.append(model_id)
        self.current["active_asr_model"] = model_id
        return dict(self.current)

    def acquire(self, session_id: str, model_id: str) -> dict[str, object]:
        self.current["leased_by"] = session_id
        return dict(self.current)

    def release(self, session_id: str) -> dict[str, object]:
        if self.current["leased_by"] == session_id:
            self.current["leased_by"] = None
        return dict(self.current)


def test_catalog_has_all_asr_and_independent_correction_choices() -> None:
    service = ModelCatalogService(worker=FakeWorkerClient(), correction_ready=lambda: True)

    catalog = service.catalog()

    assert {item.id for item in catalog.asr} == {
        "faster-whisper-small",
        "breeze-asr-25",
        "qwen3-asr-1.7b",
    }
    assert {item.id for item in catalog.correction} == {"qwen2.5-correction", "disabled"}
    assert catalog.active.asr_model == "qwen3-asr-1.7b"
    assert catalog.active.correction_model == "qwen2.5-correction"
    assert catalog.active.state == "ready"
    assert catalog.active.device == "cuda"


def test_activation_switches_asr_and_correction_without_submit_state() -> None:
    worker = FakeWorkerClient()
    service = ModelCatalogService(worker=worker, correction_ready=lambda: True)

    catalog = service.activate("breeze-asr-25", "disabled")

    assert worker.activations == ["breeze-asr-25"]
    assert catalog.active.asr_model == "breeze-asr-25"
    assert catalog.active.correction_model == "disabled"


def test_correction_model_is_reported_unavailable_when_worker_is_down() -> None:
    service = ModelCatalogService(worker=FakeWorkerClient(), correction_ready=lambda: False)

    catalog = service.catalog()

    correction = {item.id: item for item in catalog.correction}
    assert correction["qwen2.5-correction"].ready is False
    assert correction["disabled"].ready is True


def test_worker_client_uses_bounded_internal_routes() -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def request(method: str, path: str, payload: dict[str, object] | None) -> tuple[int, dict[str, object]]:
        calls.append((method, path, payload))
        return 200, dict(READY_SNAPSHOT)

    client = ASRWorkerControlClient("http://asr-worker:8771", request=request)

    client.snapshot()
    client.activate("qwen3-asr-1.7b")
    client.acquire("session-a", "qwen3-asr-1.7b")
    client.release("session-a")

    assert calls == [
        ("GET", "/internal/v1/models", None),
        ("PUT", "/internal/v1/models/active", {"asr_model": "qwen3-asr-1.7b"}),
        ("POST", "/internal/v1/models/lease/session-a?asr_model=qwen3-asr-1.7b", None),
        ("DELETE", "/internal/v1/models/lease/session-a", None),
    ]


def test_worker_client_preserves_stable_error_but_hides_unknown_body() -> None:
    responses: list[tuple[int, dict[str, Any]]] = [
        (
            409,
            {
                "error": {
                    "code": "model_in_use",
                    "message": "The active ASR model is in use by another session",
                    "stage": "asr",
                    "retryable": True,
                }
            },
        ),
        (500, {"debug": "/private/model/path"}),
    ]

    def request(*_: object) -> tuple[int, dict[str, Any]]:
        return responses.pop(0)

    client = ASRWorkerControlClient("http://asr-worker:8771", request=request)

    with pytest.raises(PlatformError) as conflict:
        client.activate("breeze-asr-25")
    with pytest.raises(PlatformError) as invalid:
        client.snapshot()

    assert conflict.value.code == "model_in_use"
    assert conflict.value.status_code == 409
    assert invalid.value.code == "asr_worker_unavailable"
    assert "/private" not in invalid.value.message
