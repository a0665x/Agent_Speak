from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from agent_speak.asr_model_manager import ASRModelManager, ModelLeaseConflict
from agent_speak.errors import PlatformError
from agent_speak.model_ids import ASRModelId


@dataclass
class FakeProvider:
    name: str
    events: list[str]
    device: str = "cpu"
    fail_warm: bool = False
    warm_hook: object | None = None
    transcriptions: list[tuple[bytes, str | None]] = field(default_factory=list)

    def warm(self) -> None:
        self.events.append(f"warm:{self.name}")
        if callable(self.warm_hook):
            self.warm_hook()
        if self.fail_warm:
            raise RuntimeError(f"failed {self.name}")

    def close(self) -> None:
        self.events.append(f"close:{self.name}")

    def transcribe(self, audio: bytes, language: str | None = None) -> str:
        self.transcriptions.append((audio, language))
        return f"{self.name}:{language}"


def make_manager(
    *,
    fail_warm: set[ASRModelId] | None = None,
    events: list[str] | None = None,
    cleanup: object | None = None,
) -> tuple[ASRModelManager, dict[ASRModelId, list[FakeProvider]], list[str]]:
    event_log = events if events is not None else []
    failures = fail_warm or set()
    instances: dict[ASRModelId, list[FakeProvider]] = {
        "faster-whisper-small": [],
        "breeze-asr-25": [],
        "qwen3-asr-1.7b": [],
    }

    def factory(model_id: ASRModelId):
        def create() -> FakeProvider:
            event_log.append(f"create:{model_id}")
            provider = FakeProvider(model_id, event_log, fail_warm=model_id in failures)
            instances[model_id].append(provider)
            return provider

        return create

    manager = ASRModelManager(
        factories={model_id: factory(model_id) for model_id in instances},
        device="cpu",
        memory_cleanup=cleanup if callable(cleanup) else lambda: event_log.append("cleanup"),
    )
    return manager, instances, event_log


def test_initial_activation_warms_and_publishes_ready_provider() -> None:
    manager, _, events = make_manager()

    snapshot = manager.activate("qwen3-asr-1.7b")

    assert snapshot.state == "ready"
    assert snapshot.active_asr_model == "qwen3-asr-1.7b"
    assert snapshot.requested_asr_model is None
    assert snapshot.leased_by is None
    assert snapshot.error_code is None
    assert events == ["create:qwen3-asr-1.7b", "warm:qwen3-asr-1.7b"]


def test_same_model_activation_is_idempotent() -> None:
    manager, instances, _ = make_manager()
    manager.activate("qwen3-asr-1.7b")

    manager.activate("qwen3-asr-1.7b")

    assert len(instances["qwen3-asr-1.7b"]) == 1


def test_switch_closes_and_cleans_old_provider_before_loading_new_one() -> None:
    manager, _, events = make_manager()
    manager.activate("qwen3-asr-1.7b")
    events.clear()

    manager.activate("breeze-asr-25")

    assert events == [
        "close:qwen3-asr-1.7b",
        "cleanup",
        "create:breeze-asr-25",
        "warm:breeze-asr-25",
    ]


def test_conflicting_activation_is_rejected_while_leased() -> None:
    manager, _, _ = make_manager()
    manager.activate("qwen3-asr-1.7b")
    manager.acquire("session-a", "qwen3-asr-1.7b")

    with pytest.raises(ModelLeaseConflict) as captured:
        manager.activate("breeze-asr-25")

    assert captured.value.code == "model_in_use"
    assert captured.value.status_code == 409
    assert manager.snapshot().active_asr_model == "qwen3-asr-1.7b"


def test_same_model_activation_is_allowed_while_leased() -> None:
    manager, _, _ = make_manager()
    manager.activate("qwen3-asr-1.7b")
    manager.acquire("session-a", "qwen3-asr-1.7b")

    snapshot = manager.activate("qwen3-asr-1.7b")

    assert snapshot.state == "ready"
    assert snapshot.leased_by == "session-a"


def test_lease_owner_controls_transcription_and_release() -> None:
    manager, instances, _ = make_manager()
    manager.activate("breeze-asr-25")
    manager.acquire("session-a", "breeze-asr-25")

    assert manager.transcribe("session-a", "breeze-asr-25", b"wav", language="zh") == "breeze-asr-25:zh"
    assert instances["breeze-asr-25"][0].transcriptions == [(b"wav", "zh")]

    with pytest.raises(ModelLeaseConflict):
        manager.transcribe("session-b", "breeze-asr-25", b"wav", language="zh")

    manager.release("session-b")
    assert manager.snapshot().leased_by == "session-a"
    manager.release("session-a")
    assert manager.snapshot().leased_by is None


def test_acquire_rejects_model_that_is_not_active() -> None:
    manager, _, _ = make_manager()
    manager.activate("qwen3-asr-1.7b")

    with pytest.raises(PlatformError) as captured:
        manager.acquire("session-a", "breeze-asr-25")

    assert captured.value.code == "model_not_ready"
    assert captured.value.status_code == 409


def test_progress_snapshot_is_visible_during_warm() -> None:
    observed: list[tuple[str, ASRModelId | None]] = []
    holder: dict[str, ASRModelManager] = {}

    def observe() -> None:
        snapshot = holder["manager"].snapshot()
        observed.append((snapshot.state, snapshot.requested_asr_model))

    def factory(model_id: ASRModelId):
        return lambda: FakeProvider(model_id, [], warm_hook=observe)

    manager = ASRModelManager(
        factories={
            model_id: factory(model_id)
            for model_id in ("faster-whisper-small", "breeze-asr-25", "qwen3-asr-1.7b")
        },
        device="cpu",
        memory_cleanup=lambda: None,
    )
    holder["manager"] = manager
    manager.activate("qwen3-asr-1.7b")
    manager.activate("breeze-asr-25")

    assert observed == [
        ("warming", "qwen3-asr-1.7b"),
        ("warming", "breeze-asr-25"),
    ]


def test_failed_warm_restores_last_ready_provider() -> None:
    manager, instances, _ = make_manager(fail_warm={"breeze-asr-25"})
    manager.activate("qwen3-asr-1.7b")

    with pytest.raises(PlatformError) as captured:
        manager.activate("breeze-asr-25")

    snapshot = manager.snapshot()
    assert captured.value.code == "model_activation_failed"
    assert snapshot.active_asr_model == "qwen3-asr-1.7b"
    assert snapshot.state == "ready"
    assert snapshot.error_code == "model_activation_failed"
    assert len(instances["qwen3-asr-1.7b"]) == 2


def test_failed_initial_warm_leaves_manager_failed() -> None:
    manager, _, _ = make_manager(fail_warm={"qwen3-asr-1.7b"})

    with pytest.raises(PlatformError):
        manager.activate("qwen3-asr-1.7b")

    snapshot = manager.snapshot()
    assert snapshot.state == "failed"
    assert snapshot.active_asr_model is None
    assert snapshot.error_code == "model_activation_failed"


def test_failed_rollback_leaves_manager_unavailable() -> None:
    manager, instances, _ = make_manager(fail_warm={"breeze-asr-25"})
    manager.activate("qwen3-asr-1.7b")
    # Make only the reconstructed rollback provider fail.
    original_factory = manager.factories["qwen3-asr-1.7b"]

    def failing_rollback_factory() -> FakeProvider:
        provider = original_factory()
        if len(instances["qwen3-asr-1.7b"]) > 1:
            provider.fail_warm = True
        return provider

    manager.factories["qwen3-asr-1.7b"] = failing_rollback_factory

    with pytest.raises(PlatformError) as captured:
        manager.activate("breeze-asr-25")

    snapshot = manager.snapshot()
    assert captured.value.code == "model_rollback_failed"
    assert snapshot.state == "failed"
    assert snapshot.active_asr_model is None
    assert snapshot.error_code == "model_rollback_failed"


def test_unknown_model_is_bounded_validation_error() -> None:
    manager, _, _ = make_manager()

    with pytest.raises(PlatformError) as captured:
        manager.activate("unknown")  # type: ignore[arg-type]

    assert captured.value.code == "unknown_asr_model"
    assert captured.value.status_code == 422
