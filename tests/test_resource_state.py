from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from agent_speak.resource_state import ResourceStateError, ResourceStateStore
from agent_speak.resource_types import (
    OperationPhase,
    ResourceOperation,
    ResourcePolicy,
    ResourceProfile,
    ResourceSnapshot,
    Workload,
    WorkloadLifecycle,
    WorkloadStatus,
)


def ready_asr_snapshot() -> ResourceSnapshot:
    return ResourceSnapshot(
        requested_policy=ResourcePolicy.AUTO,
        resolved_policy=ResourcePolicy.EXCLUSIVE,
        profile=ResourceProfile.ASR_ONLY,
        desired_workloads=frozenset({Workload.ASR, Workload.CORRECTION}),
        workloads={
            Workload.ASR: WorkloadStatus(
                workload=Workload.ASR,
                desired=True,
                lifecycle=WorkloadLifecycle.READY,
                ready=True,
                model="qwen3-asr-1.7b",
                device="cuda",
            ),
            Workload.CORRECTION: WorkloadStatus(
                workload=Workload.CORRECTION,
                desired=True,
                lifecycle=WorkloadLifecycle.READY,
                ready=True,
                model="qwen2.5-correction",
                device="nvidia",
            ),
            Workload.AGENT: WorkloadStatus.stopped(Workload.AGENT),
            Workload.TTS: WorkloadStatus.stopped(Workload.TTS),
        },
        operation=ResourceOperation(
            id="op_6f57d9d8567b4fb5",
            action="reconcile",
            target="asr_only",
            phase=OperationPhase.READY,
            created_at="2026-07-23T07:30:00Z",
            updated_at="2026-07-23T07:30:03Z",
        ),
        last_ready_profile=ResourceProfile.ASR_ONLY,
    )


def test_state_store_round_trips_one_bounded_snapshot(tmp_path: Path) -> None:
    store = ResourceStateStore(tmp_path / "resource-control" / "state.json")
    snapshot = ready_asr_snapshot()

    store.write(snapshot)

    assert store.read() == snapshot
    assert not list(tmp_path.rglob("*.tmp"))
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700


def test_state_store_replaces_existing_snapshot_atomically(tmp_path: Path) -> None:
    store = ResourceStateStore(tmp_path / "state.json")
    first = ready_asr_snapshot()
    store.write(first)
    second = ResourceSnapshot.initial(
        requested_policy=ResourcePolicy.EXCLUSIVE,
        resolved_policy=ResourcePolicy.EXCLUSIVE,
        profile=ResourceProfile.TTS_ONLY,
    )

    store.write(second)

    assert store.read() == second
    assert json.loads(store.path.read_text(encoding="utf-8")) == second.to_dict()


def test_state_store_rejects_oversized_json(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        '{"private_text":"' + ("x" * 70_000) + '"}',
        encoding="utf-8",
    )

    with pytest.raises(ResourceStateError, match="exceeds"):
        ResourceStateStore(path, max_bytes=64 * 1024).read()


def test_state_store_rejects_unknown_private_fields(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    payload = ready_asr_snapshot().to_dict()
    payload["exception_message"] = "private provider path"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResourceStateError, match="invalid"):
        ResourceStateStore(path).read()


def test_state_store_rejects_invalid_operation_id_without_rewriting(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    payload = ready_asr_snapshot().to_dict()
    assert isinstance(payload["operation"], dict)
    payload["operation"]["id"] = "../../bad"
    original = json.dumps(payload)
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ResourceStateError, match="invalid"):
        ResourceStateStore(path).read()

    assert path.read_text(encoding="utf-8") == original
