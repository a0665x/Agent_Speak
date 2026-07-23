from __future__ import annotations

import json
import stat
from pathlib import Path
from threading import Event

import pytest

from agent_speak.resource_supervisor import (
    ComposeLifecycleAdapter,
    ResourceSupervisor,
    ResourceSupervisorError,
    ResourceUnixServer,
    resolve_usable_memory_mb,
)
from agent_speak.resource_types import (
    OperationPhase,
    ResourcePolicy,
    ResourceProfile,
    Workload,
)


class FakeLifecycle:
    def __init__(self, ready: set[Workload]) -> None:
        self.ready = set(ready)
        self.calls: list[tuple[str, Workload]] = []

    def stop(self, workload: Workload) -> None:
        self.calls.append(("stop", workload))
        self.ready.discard(workload)

    def start(self, workload: Workload) -> None:
        self.calls.append(("start", workload))
        self.ready.add(workload)

    def is_ready(self, workload: Workload) -> bool:
        return workload in self.ready

    def usable_gpu_memory_mb(self) -> int:
        return 48_000


class BlockingLifecycle(FakeLifecycle):
    def __init__(self) -> None:
        super().__init__({Workload.ASR, Workload.CORRECTION})
        self.release = Event()

    def stop(self, workload: Workload) -> None:
        self.release.wait(timeout=2)
        super().stop(workload)


class FailingTTSLifecycle(FakeLifecycle):
    def start(self, workload: Workload) -> None:
        self.calls.append(("start", workload))
        if workload is Workload.TTS:
            raise RuntimeError("private driver failure at /private/path")
        self.ready.add(workload)


def supervisor(
    tmp_path: Path,
    lifecycle: FakeLifecycle,
    policy: ResourcePolicy,
) -> ResourceSupervisor:
    return ResourceSupervisor.for_test(
        lifecycle=lifecycle,
        state_path=tmp_path / "state.json",
        policy=policy,
        start_timeout=0.2,
    )


def test_exclusive_reset_releases_peer_before_starting_target(
    tmp_path: Path,
) -> None:
    lifecycle = FakeLifecycle({Workload.ASR, Workload.CORRECTION})
    control = supervisor(tmp_path, lifecycle, ResourcePolicy.EXCLUSIVE)

    operation = control.reset(Workload.TTS)
    completed = control.wait(operation.id, timeout=1)

    assert lifecycle.calls == [
        ("stop", Workload.CORRECTION),
        ("stop", Workload.ASR),
        ("start", Workload.TTS),
    ]
    assert completed.phase is OperationPhase.READY
    assert control.snapshot().desired_workloads == frozenset({Workload.TTS})
    assert control.snapshot().profile is ResourceProfile.TTS_ONLY


def test_concurrent_reset_keeps_ready_peer_resident(tmp_path: Path) -> None:
    lifecycle = FakeLifecycle({Workload.ASR, Workload.CORRECTION})
    control = supervisor(tmp_path, lifecycle, ResourcePolicy.CONCURRENT)

    operation = control.reset(Workload.TTS)
    completed = control.wait(operation.id, timeout=1)

    assert lifecycle.calls == [("start", Workload.TTS)]
    assert completed.phase is OperationPhase.READY
    assert control.snapshot().desired_workloads == frozenset(
        {Workload.ASR, Workload.CORRECTION, Workload.TTS}
    )
    assert control.snapshot().profile is None


def test_reconcile_is_exact_even_under_concurrent_policy(tmp_path: Path) -> None:
    lifecycle = FakeLifecycle(
        {Workload.ASR, Workload.CORRECTION, Workload.TTS}
    )
    control = supervisor(tmp_path, lifecycle, ResourcePolicy.CONCURRENT)

    operation = control.reconcile(ResourceProfile.TTS_ONLY)
    control.wait(operation.id, timeout=1)

    assert lifecycle.calls == [
        ("stop", Workload.CORRECTION),
        ("stop", Workload.ASR),
    ]
    assert control.snapshot().desired_workloads == frozenset({Workload.TTS})


def test_incompatible_requests_share_one_serial_operation(tmp_path: Path) -> None:
    lifecycle = BlockingLifecycle()
    control = supervisor(tmp_path, lifecycle, ResourcePolicy.EXCLUSIVE)

    first = control.reset(Workload.TTS)
    second = control.reset(Workload.ASR)

    assert second.id == first.id
    lifecycle.release.set()
    assert control.wait(first.id, timeout=1).phase is OperationPhase.READY


def test_same_ready_target_is_idempotent(tmp_path: Path) -> None:
    lifecycle = FakeLifecycle({Workload.ASR, Workload.CORRECTION})
    control = supervisor(tmp_path, lifecycle, ResourcePolicy.EXCLUSIVE)

    first = control.reconcile(ResourceProfile.ASR_ONLY)
    second = control.reconcile(ResourceProfile.ASR_ONLY)

    assert first.id == second.id
    assert first.phase is OperationPhase.READY
    assert lifecycle.calls == []


def test_full_pipeline_refuses_development_agent(tmp_path: Path) -> None:
    control = supervisor(
        tmp_path,
        FakeLifecycle({Workload.ASR, Workload.CORRECTION}),
        ResourcePolicy.CONCURRENT,
    )

    with pytest.raises(
        ResourceSupervisorError,
        match="agent_provider_unavailable",
    ):
        control.reconcile(ResourceProfile.FULL_PIPELINE)


def test_failed_start_rolls_back_once_without_private_error_text(
    tmp_path: Path,
) -> None:
    lifecycle = FailingTTSLifecycle({Workload.ASR, Workload.CORRECTION})
    control = supervisor(tmp_path, lifecycle, ResourcePolicy.EXCLUSIVE)

    operation = control.reset(Workload.TTS)
    completed = control.wait(operation.id, timeout=1)

    assert completed.phase is OperationPhase.ROLLED_BACK
    assert completed.error_code == "workload_start_failed"
    assert control.snapshot().desired_workloads == frozenset(
        {Workload.ASR, Workload.CORRECTION}
    )
    persisted = (tmp_path / "state.json").read_text(encoding="utf-8")
    assert "private driver" not in persisted
    assert "/private/path" not in persisted
    assert lifecycle.calls.count(("start", Workload.TTS)) == 1


def test_unix_server_prepares_private_path_and_bounded_dispatch_protocol(
    tmp_path: Path,
) -> None:
    lifecycle = FakeLifecycle({Workload.ASR, Workload.CORRECTION})
    control = supervisor(tmp_path, lifecycle, ResourcePolicy.EXCLUSIVE)
    socket_path = tmp_path / "control" / "control.sock"
    server = ResourceUnixServer(socket_path, control)
    server.prepare_path()
    payload = server.dispatch({"action": "snapshot"})

    assert payload["ok"] is True
    assert payload["result"]["resolved_policy"] == "exclusive"
    assert stat.S_IMODE(socket_path.parent.stat().st_mode) == 0o700
    assert server.socket_mode == 0o600


def test_unix_server_rejects_unknown_action_without_echoing_request(
    tmp_path: Path,
) -> None:
    control = supervisor(
        tmp_path,
        FakeLifecycle({Workload.ASR, Workload.CORRECTION}),
        ResourcePolicy.EXCLUSIVE,
    )
    server = ResourceUnixServer(tmp_path / "control.sock", control)

    response = server.dispatch(
        {"action": "run", "command": "rm private-recording.wav"}
    )

    assert response == {
        "ok": False,
        "error": {
            "code": "invalid_resource_action",
            "retryable": False,
        },
    }
    assert "private-recording" not in json.dumps(response)


def test_compose_adapter_uses_fixed_argument_arrays_and_parses_gpu_memory() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], timeout: float) -> str:
        calls.append(argv)
        assert timeout == 12
        if argv[0] == "nvidia-smi":
            return "0, 49140, 47000\n"
        if argv[-3:] == ["ps", "-q", "tts-worker"]:
            return "container-id\n"
        if argv[0] == "docker" and argv[1] == "inspect":
            return "healthy\n"
        return ""

    adapter = ComposeLifecycleAdapter(
        compose_prefix=["docker", "compose", "-f", "compose.yaml"],
        runner=runner,
        command_timeout=12,
    )

    adapter.start(Workload.TTS)
    assert adapter.is_ready(Workload.TTS) is True
    assert adapter.usable_gpu_memory_mb() == 49_140
    assert calls[0] == [
        "docker",
        "compose",
        "-f",
        "compose.yaml",
        "--profile",
        "tts",
        "up",
        "-d",
        "--no-deps",
        "tts-worker",
    ]

    with pytest.raises(ResourceSupervisorError, match="unsupported_workload"):
        adapter.start(Workload.AGENT)


def test_cpu_supervisor_does_not_probe_nvidia_inventory() -> None:
    lifecycle = FakeLifecycle(set())

    assert resolve_usable_memory_mb(lifecycle, "cpu") == 1
    assert lifecycle.calls == []
