"""Host-owned worker resource orchestration and private Unix protocol."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
from threading import Condition, Event, Lock, Thread
import time
from typing import Any, Protocol
from uuid import uuid4

from .resource_state import ResourceStateStore
from .resource_types import (
    MemoryBudget,
    OperationPhase,
    ResourceOperation,
    ResourcePolicy,
    ResourceProfile,
    ResourceSnapshot,
    Workload,
    WorkloadLifecycle,
    WorkloadStatus,
    plan_profile,
    resolve_policy,
)


TERMINAL_PHASES = {
    OperationPhase.READY,
    OperationPhase.FAILED,
    OperationPhase.ROLLED_BACK,
    OperationPhase.CANCELLED,
}
START_ORDER = (Workload.ASR, Workload.CORRECTION, Workload.TTS)
STOP_ORDER = (Workload.CORRECTION, Workload.ASR, Workload.TTS)
MODEL_NAMES = {
    Workload.ASR: "asr",
    Workload.CORRECTION: "qwen2.5-correction",
    Workload.AGENT: "unavailable",
    Workload.TTS: "voxcpm2",
}
DEVICE_NAMES = {
    Workload.ASR: "cuda",
    Workload.CORRECTION: "nvidia",
    Workload.AGENT: "unavailable",
    Workload.TTS: "cuda",
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class ResourceSupervisorError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class LifecycleAdapter(Protocol):
    def start(self, workload: Workload) -> None:
        raise NotImplementedError

    def stop(self, workload: Workload) -> None:
        raise NotImplementedError

    def is_ready(self, workload: Workload) -> bool:
        raise NotImplementedError

    def usable_gpu_memory_mb(self) -> int:
        raise NotImplementedError


class ResourceSupervisor:
    def __init__(
        self,
        *,
        lifecycle: LifecycleAdapter,
        store: ResourceStateStore,
        snapshot: ResourceSnapshot,
        start_timeout: float = 300.0,
        poll_interval: float = 0.05,
        agent_ready: bool = False,
    ) -> None:
        self.lifecycle = lifecycle
        self.store = store
        self._snapshot = snapshot
        self.start_timeout = start_timeout
        self.poll_interval = poll_interval
        self.agent_ready = agent_ready
        self._lock = Lock()
        self._condition = Condition(self._lock)
        self._thread: Thread | None = None
        self.store.write(snapshot)

    @classmethod
    def for_test(
        cls,
        *,
        lifecycle: LifecycleAdapter,
        state_path: Path,
        policy: ResourcePolicy,
        start_timeout: float = 0.2,
    ) -> "ResourceSupervisor":
        asr_ready = lifecycle.is_ready(Workload.ASR)
        correction_ready = lifecycle.is_ready(Workload.CORRECTION)
        tts_ready = lifecycle.is_ready(Workload.TTS)
        if tts_ready and not asr_ready:
            profile: ResourceProfile | None = ResourceProfile.TTS_ONLY
            desired = frozenset({Workload.TTS})
        elif asr_ready or correction_ready:
            profile = ResourceProfile.ASR_ONLY
            desired = frozenset({Workload.ASR, Workload.CORRECTION})
        else:
            profile = ResourceProfile.ASR_ONLY
            desired = frozenset(plan_profile(profile))
        workloads = {
            workload: cls._observed_status(
                lifecycle,
                workload,
                desired=workload in desired,
            )
            for workload in Workload
        }
        snapshot = ResourceSnapshot(
            requested_policy=policy,
            resolved_policy=policy,
            profile=profile,
            desired_workloads=desired,
            workloads=workloads,
            operation=None,
            last_ready_profile=(
                profile
                if all(
                    workloads[item].ready
                    for item in desired
                )
                else None
            ),
        )
        return cls(
            lifecycle=lifecycle,
            store=ResourceStateStore(state_path),
            snapshot=snapshot,
            start_timeout=start_timeout,
        )

    @staticmethod
    def _observed_status(
        lifecycle: LifecycleAdapter,
        workload: Workload,
        *,
        desired: bool,
    ) -> WorkloadStatus:
        ready = lifecycle.is_ready(workload)
        return WorkloadStatus(
            workload=workload,
            desired=desired,
            lifecycle=(
                WorkloadLifecycle.READY
                if ready
                else WorkloadLifecycle.STOPPED
            ),
            ready=ready,
            model=MODEL_NAMES[workload] if ready else None,
            device=DEVICE_NAMES[workload] if ready else "unavailable",
        )

    def snapshot(self) -> ResourceSnapshot:
        with self._lock:
            return self._snapshot

    def reconcile(self, profile: ResourceProfile) -> ResourceOperation:
        if (
            profile is ResourceProfile.FULL_PIPELINE
            and not self.agent_ready
        ):
            raise ResourceSupervisorError("agent_provider_unavailable")
        return self._request_operation(
            action="reconcile",
            target=profile.value,
            desired=frozenset(plan_profile(profile)),
            profile=profile,
        )

    def reset(self, workload: Workload) -> ResourceOperation:
        if workload is Workload.AGENT and not self.agent_ready:
            raise ResourceSupervisorError("agent_provider_unavailable")
        with self._lock:
            current = self._snapshot
            if current.resolved_policy is ResourcePolicy.EXCLUSIVE:
                if workload is Workload.TTS:
                    desired = frozenset({Workload.TTS})
                    profile: ResourceProfile | None = ResourceProfile.TTS_ONLY
                else:
                    desired = frozenset(
                        {Workload.ASR, Workload.CORRECTION}
                    )
                    profile = ResourceProfile.ASR_ONLY
            else:
                desired_set = set(current.desired_workloads)
                desired_set.add(workload)
                if workload is Workload.ASR:
                    desired_set.add(Workload.CORRECTION)
                desired = frozenset(desired_set)
                profile = self._profile_for(desired)
        return self._request_operation(
            action="reset",
            target=workload.value,
            desired=desired,
            profile=profile,
            force_restart=workload,
        )

    @staticmethod
    def _profile_for(
        desired: frozenset[Workload],
    ) -> ResourceProfile | None:
        for profile in (
            ResourceProfile.ASR_ONLY,
            ResourceProfile.TTS_ONLY,
            ResourceProfile.FULL_PIPELINE,
        ):
            if desired == frozenset(plan_profile(profile)):
                return profile
        return None

    def _request_operation(
        self,
        *,
        action: str,
        target: str,
        desired: frozenset[Workload],
        profile: ResourceProfile | None,
        force_restart: Workload | None = None,
    ) -> ResourceOperation:
        with self._condition:
            active = self._snapshot.operation
            if active is not None and active.phase not in TERMINAL_PHASES:
                return active
            if (
                action == "reconcile"
                and self._snapshot.desired_workloads == desired
                and all(
                    self._snapshot.workloads[item].ready for item in desired
                )
            ):
                if (
                    active is not None
                    and active.action == action
                    and active.target == target
                    and active.phase is OperationPhase.READY
                ):
                    return active
                operation = self._new_operation(
                    action=action,
                    target=target,
                    phase=OperationPhase.READY,
                )
                self._snapshot = replace(
                    self._snapshot,
                    profile=profile,
                    operation=operation,
                    last_ready_profile=profile,
                )
                self.store.write(self._snapshot)
                return operation

            previous = self._snapshot
            operation = self._new_operation(
                action=action,
                target=target,
                phase=OperationPhase.QUEUED,
            )
            workloads = {
                item: replace(
                    status,
                    desired=item in desired,
                )
                for item, status in previous.workloads.items()
            }
            self._snapshot = replace(
                previous,
                profile=profile,
                desired_workloads=desired,
                workloads=workloads,
                operation=operation,
            )
            self.store.write(self._snapshot)
            self._thread = Thread(
                target=self._execute,
                args=(previous, desired, profile, force_restart),
                daemon=True,
                name=f"resource-{operation.id}",
            )
            self._thread.start()
            return operation

    @staticmethod
    def _new_operation(
        *,
        action: str,
        target: str,
        phase: OperationPhase,
    ) -> ResourceOperation:
        now = _utc_now()
        return ResourceOperation(
            id=f"op_{uuid4().hex[:16]}",
            action=action,
            target=target,
            phase=phase,
            created_at=now,
            updated_at=now,
        )

    def _set_phase(
        self,
        phase: OperationPhase,
        *,
        error_code: str | None = None,
        operator_hint: str | None = None,
    ) -> None:
        with self._condition:
            operation = self._snapshot.operation
            if operation is None:
                raise ResourceSupervisorError("resource_operation_missing")
            operation = replace(
                operation,
                phase=phase,
                updated_at=_utc_now(),
                error_code=error_code,
                operator_hint=operator_hint,
            )
            self._snapshot = replace(
                self._snapshot,
                operation=operation,
            )
            self.store.write(self._snapshot)
            self._condition.notify_all()

    def _set_workload(
        self,
        workload: Workload,
        lifecycle: WorkloadLifecycle,
        *,
        error_code: str | None = None,
    ) -> None:
        with self._condition:
            current = self._snapshot.workloads[workload]
            ready = lifecycle is WorkloadLifecycle.READY
            updated = replace(
                current,
                lifecycle=lifecycle,
                ready=ready,
                model=MODEL_NAMES[workload] if ready else None,
                device=DEVICE_NAMES[workload] if ready else "unavailable",
                error_code=error_code,
                operator_hint=(
                    self._operator_hint(workload)
                    if error_code is not None
                    else None
                ),
            )
            workloads = dict(self._snapshot.workloads)
            workloads[workload] = updated
            self._snapshot = replace(self._snapshot, workloads=workloads)
            self.store.write(self._snapshot)
            self._condition.notify_all()

    @staticmethod
    def _operator_hint(workload: Workload) -> str:
        service = {
            Workload.ASR: "asr-worker",
            Workload.CORRECTION: "correction-worker",
            Workload.TTS: "tts-worker",
            Workload.AGENT: "gateway",
        }[workload]
        return f"./run.sh --logs {service}"

    def _execute(
        self,
        previous: ResourceSnapshot,
        desired: frozenset[Workload],
        profile: ResourceProfile | None,
        force_restart: Workload | None,
    ) -> None:
        current_step = "release"
        current_workload = Workload.TTS
        try:
            ready_before = {
                item
                for item in Workload
                if self.lifecycle.is_ready(item)
            }
            to_stop = set(ready_before - set(desired))
            if force_restart is not None and force_restart in ready_before:
                to_stop.add(force_restart)
            if to_stop:
                self._set_phase(OperationPhase.DRAINING)
                for workload in STOP_ORDER:
                    if workload not in to_stop:
                        continue
                    current_workload = workload
                    self._set_workload(
                        workload,
                        WorkloadLifecycle.DRAINING,
                    )
                    self.lifecycle.stop(workload)
                    self._set_workload(
                        workload,
                        WorkloadLifecycle.STOPPED,
                    )
                self._set_phase(OperationPhase.RELEASING)

            to_start = {
                item
                for item in desired
                if not self.lifecycle.is_ready(item)
            }
            current_step = "start"
            if to_start:
                self._set_phase(OperationPhase.STARTING)
            for workload in START_ORDER:
                if workload not in to_start:
                    continue
                current_workload = workload
                self._set_workload(
                    workload,
                    WorkloadLifecycle.STARTING,
                )
                self.lifecycle.start(workload)
                self._set_phase(OperationPhase.WARMING)
                self._set_workload(
                    workload,
                    WorkloadLifecycle.WARMING,
                )
                deadline = time.monotonic() + self.start_timeout
                while not self.lifecycle.is_ready(workload):
                    if time.monotonic() >= deadline:
                        raise ResourceSupervisorError(
                            "workload_start_timeout",
                            retryable=True,
                        )
                    time.sleep(self.poll_interval)
                self._set_workload(
                    workload,
                    WorkloadLifecycle.READY,
                )

            with self._condition:
                self._snapshot = replace(
                    self._snapshot,
                    profile=profile,
                    last_ready_profile=profile,
                )
                self.store.write(self._snapshot)
            self._set_phase(OperationPhase.READY)
        except Exception:
            code = (
                "workload_start_failed"
                if current_step == "start"
                else "workload_stop_failed"
            )
            self._rollback(previous, code, current_workload)

    def _rollback(
        self,
        previous: ResourceSnapshot,
        error_code: str,
        failed_workload: Workload,
    ) -> None:
        try:
            previous_desired = set(previous.desired_workloads)
            for workload in STOP_ORDER:
                if (
                    workload not in previous_desired
                    and self.lifecycle.is_ready(workload)
                ):
                    self.lifecycle.stop(workload)
            for workload in START_ORDER:
                if (
                    workload in previous_desired
                    and not self.lifecycle.is_ready(workload)
                ):
                    self.lifecycle.start(workload)
                    deadline = time.monotonic() + self.start_timeout
                    while not self.lifecycle.is_ready(workload):
                        if time.monotonic() >= deadline:
                            raise ResourceSupervisorError(
                                "rollback_timeout"
                            )
                        time.sleep(self.poll_interval)
            workloads = {
                workload: self._observed_status(
                    self.lifecycle,
                    workload,
                    desired=workload in previous_desired,
                )
                for workload in Workload
            }
            with self._condition:
                operation = self._snapshot.operation
                if operation is None:
                    raise ResourceSupervisorError(
                        "resource_operation_missing"
                    )
                operation = replace(
                    operation,
                    phase=OperationPhase.ROLLED_BACK,
                    updated_at=_utc_now(),
                    error_code=error_code,
                    operator_hint=self._operator_hint(failed_workload),
                )
                self._snapshot = replace(
                    previous,
                    workloads=workloads,
                    operation=operation,
                )
                self.store.write(self._snapshot)
                self._condition.notify_all()
        except Exception:
            self._set_phase(
                OperationPhase.FAILED,
                error_code="resource_rollback_failed",
                operator_hint="./run.sh --status",
            )

    def wait(
        self,
        operation_id: str,
        *,
        timeout: float,
    ) -> ResourceOperation:
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                operation = self._snapshot.operation
                if operation is None or operation.id != operation_id:
                    raise ResourceSupervisorError(
                        "resource_operation_not_found"
                    )
                if operation.phase in TERMINAL_PHASES:
                    return operation
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ResourceSupervisorError(
                        "resource_operation_wait_timeout",
                        retryable=True,
                    )
                self._condition.wait(timeout=remaining)

    def operation(self, operation_id: str) -> ResourceOperation:
        with self._lock:
            operation = self._snapshot.operation
            if operation is None or operation.id != operation_id:
                raise ResourceSupervisorError(
                    "resource_operation_not_found"
                )
            return operation


Runner = Callable[[list[str], float], str]


def _run_command(argv: list[str], timeout: float) -> str:
    result = subprocess.run(
        argv,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout


class ComposeLifecycleAdapter:
    START_COMMANDS: dict[Workload, tuple[str, ...]] = {
        Workload.ASR: (
            "--profile",
            "asr",
            "up",
            "-d",
            "--no-deps",
            "asr-worker",
        ),
        Workload.CORRECTION: (
            "--profile",
            "asr",
            "up",
            "-d",
            "--no-deps",
            "correction-worker",
        ),
        Workload.TTS: (
            "--profile",
            "tts",
            "up",
            "-d",
            "--no-deps",
            "tts-worker",
        ),
    }
    SERVICES = {
        Workload.ASR: ("asr", "asr-worker"),
        Workload.CORRECTION: ("asr", "correction-worker"),
        Workload.TTS: ("tts", "tts-worker"),
    }

    def __init__(
        self,
        *,
        compose_prefix: Sequence[str],
        runner: Runner = _run_command,
        command_timeout: float = 30.0,
        gpu_devices: Sequence[int] | None = None,
    ) -> None:
        self.compose_prefix = list(compose_prefix)
        self.runner = runner
        self.command_timeout = command_timeout
        self.gpu_devices = tuple(gpu_devices or (0,))

    def _run(self, argv: list[str]) -> str:
        try:
            return self.runner(argv, self.command_timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ResourceSupervisorError(
                "lifecycle_command_failed",
                retryable=True,
            ) from exc

    def start(self, workload: Workload) -> None:
        command = self.START_COMMANDS.get(workload)
        if command is None:
            raise ResourceSupervisorError("unsupported_workload")
        self._run([*self.compose_prefix, *command])

    def stop(self, workload: Workload) -> None:
        service = self.SERVICES.get(workload)
        if service is None:
            raise ResourceSupervisorError("unsupported_workload")
        profile, name = service
        self._run(
            [
                *self.compose_prefix,
                "--profile",
                profile,
                "stop",
                name,
            ]
        )

    def is_ready(self, workload: Workload) -> bool:
        service = self.SERVICES.get(workload)
        if service is None:
            return False
        profile, name = service
        container_id = self._run(
            [
                *self.compose_prefix,
                "--profile",
                profile,
                "ps",
                "-q",
                name,
            ]
        ).strip()
        if not container_id:
            return False
        health = self._run(
            [
                "docker",
                "inspect",
                "--format",
                (
                    "{{if .State.Health}}{{.State.Health.Status}}"
                    "{{else}}{{.State.Status}}{{end}}"
                ),
                container_id,
            ]
        ).strip()
        return health == "healthy"

    def usable_gpu_memory_mb(self) -> int:
        output = self._run(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ]
        )
        totals: dict[int, int] = {}
        for line in output.splitlines():
            parts = [item.strip() for item in line.split(",")]
            if len(parts) != 3:
                raise ResourceSupervisorError("invalid_gpu_inventory")
            try:
                index, total, free = (int(item) for item in parts)
            except ValueError as exc:
                raise ResourceSupervisorError(
                    "invalid_gpu_inventory"
                ) from exc
            if index < 0 or total <= 0 or free < 0 or free > total:
                raise ResourceSupervisorError("invalid_gpu_inventory")
            totals[index] = total
        if not self.gpu_devices or any(
            index not in totals for index in self.gpu_devices
        ):
            raise ResourceSupervisorError("gpu_assignment_unavailable")
        return sum(totals[index] for index in self.gpu_devices)


class ResourceUnixServer:
    socket_mode = 0o600

    def __init__(
        self,
        path: Path,
        supervisor: ResourceSupervisor,
        *,
        max_request_bytes: int = 16 * 1024,
        max_response_bytes: int = 64 * 1024,
    ) -> None:
        self.path = path
        self.supervisor = supervisor
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self._shutdown = Event()
        self._ready = Event()

    def start_background(self) -> Thread:
        thread = Thread(
            target=self.serve_forever,
            daemon=True,
            name="resource-unix-server",
        )
        thread.start()
        return thread

    def wait_until_ready(self, timeout: float) -> bool:
        return self._ready.wait(timeout)

    def prepare_path(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        if self.path.exists() or self.path.is_symlink():
            mode = self.path.lstat().st_mode
            if not stat.S_ISSOCK(mode):
                raise ResourceSupervisorError("unsafe_control_socket_path")
            self.path.unlink()

    def serve_forever(self) -> None:
        self.prepare_path()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(str(self.path))
            os.chmod(self.path, self.socket_mode)
            server.listen(4)
            server.settimeout(0.2)
            self._ready.set()
            while not self._shutdown.is_set():
                try:
                    connection, _ = server.accept()
                except socket.timeout:
                    continue
                with connection:
                    response = self._read_and_dispatch(connection)
                    encoded = (
                        json.dumps(
                            response,
                            separators=(",", ":"),
                            sort_keys=True,
                        ).encode("utf-8")
                        + b"\n"
                    )
                    if len(encoded) > self.max_response_bytes:
                        encoded = (
                            b'{"error":{"code":"resource_response_too_large",'
                            b'"retryable":false},"ok":false}\n'
                        )
                    connection.sendall(encoded)
        finally:
            server.close()
            if self.path.exists() and stat.S_ISSOCK(
                self.path.lstat().st_mode
            ):
                self.path.unlink()
            self._ready.clear()

    def _read_and_dispatch(
        self,
        connection: socket.socket,
    ) -> dict[str, object]:
        connection.settimeout(2)
        payload = bytearray()
        while len(payload) <= self.max_request_bytes:
            chunk = connection.recv(
                min(4096, self.max_request_bytes + 1 - len(payload))
            )
            if not chunk:
                break
            payload.extend(chunk)
            if b"\n" in chunk:
                break
        if len(payload) > self.max_request_bytes or b"\n" not in payload:
            return self._error("invalid_resource_request")
        line = bytes(payload).split(b"\n", 1)[0]
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._error("invalid_resource_request")
        if not isinstance(value, dict):
            return self._error("invalid_resource_request")
        return self.dispatch(value)

    @staticmethod
    def _error(
        code: str,
        *,
        retryable: bool = False,
    ) -> dict[str, object]:
        return {
            "ok": False,
            "error": {
                "code": code,
                "retryable": retryable,
            },
        }

    def dispatch(self, request: dict[str, object]) -> dict[str, object]:
        action = request.get("action")
        try:
            if action == "ping" and set(request) == {"action"}:
                result: object = {"status": "ok"}
            elif action == "snapshot" and set(request) == {"action"}:
                result = self.supervisor.snapshot().to_dict()
            elif action == "reconcile" and set(request) == {
                "action",
                "profile",
            }:
                result = self.supervisor.reconcile(
                    ResourceProfile(request["profile"])
                ).to_dict()
            elif action == "reset" and set(request) == {
                "action",
                "workload",
            }:
                result = self.supervisor.reset(
                    Workload(request["workload"])
                ).to_dict()
            elif action == "operation" and set(request) == {
                "action",
                "operation_id",
            }:
                operation_id = request["operation_id"]
                if not isinstance(operation_id, str):
                    return self._error("invalid_resource_request")
                result = self.supervisor.operation(operation_id).to_dict()
            elif action == "shutdown" and set(request) == {"action"}:
                result = {"status": "stopping"}
                self._shutdown.set()
            else:
                return self._error("invalid_resource_action")
            return {"ok": True, "result": result}
        except (ValueError, ResourceSupervisorError) as exc:
            code = (
                exc.code
                if isinstance(exc, ResourceSupervisorError)
                else "invalid_resource_request"
            )
            return self._error(
                code,
                retryable=(
                    exc.retryable
                    if isinstance(exc, ResourceSupervisorError)
                    else False
                ),
            )

    def shutdown(self) -> None:
        self._shutdown.set()
        if not self.path.exists():
            return
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.2)
                client.connect(str(self.path))
                client.sendall(b'{"action":"ping"}\n')
                client.recv(1024)
        except OSError:
            pass


def _socket_request(
    path: Path,
    request: dict[str, object],
    *,
    timeout: float = 5.0,
) -> dict[str, object]:
    encoded = json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(path))
        client.sendall(encoded)
        response = client.makefile("rb").readline(64 * 1024 + 1)
    if len(response) > 64 * 1024:
        raise ResourceSupervisorError("resource_response_too_large")
    value = json.loads(response)
    if not isinstance(value, dict):
        raise ResourceSupervisorError("invalid_resource_response")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--compose-file", action="append", default=[])
    parser.add_argument(
        "--policy",
        choices=[item.value for item in ResourcePolicy],
        default=ResourcePolicy.AUTO.value,
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    subparsers.add_parser("server")
    client = subparsers.add_parser("client")
    client.add_argument(
        "action",
        choices=["ping", "snapshot", "reconcile", "reset", "operation", "shutdown"],
    )
    client.add_argument("target", nargs="?")
    client.add_argument("--wait", action="store_true")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.mode == "client":
        request: dict[str, object] = {"action": args.action}
        if args.action == "reconcile":
            request["profile"] = args.target
        elif args.action == "reset":
            request["workload"] = args.target
        elif args.action == "operation":
            request["operation_id"] = args.target
        response = _socket_request(args.socket, request)
        print(json.dumps(response, separators=(",", ":"), sort_keys=True))
        if not response.get("ok"):
            raise SystemExit(1)
        if args.wait and args.action in {"reconcile", "reset"}:
            result = response.get("result")
            if not isinstance(result, dict) or not isinstance(
                result.get("id"), str
            ):
                raise SystemExit(1)
            operation_id = result["id"]
            while True:
                current = _socket_request(
                    args.socket,
                    {
                        "action": "operation",
                        "operation_id": operation_id,
                    },
                )
                operation = current.get("result")
                if not isinstance(operation, dict):
                    raise SystemExit(1)
                if operation.get("phase") in {
                    item.value for item in TERMINAL_PHASES
                }:
                    print(
                        json.dumps(
                            current,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                    )
                    raise SystemExit(
                        0 if operation.get("phase") == "ready" else 1
                    )
                time.sleep(0.5)
        return

    compose_files = args.compose_file or [str(args.root / "compose.yaml")]
    compose_prefix = ["docker", "compose"]
    for compose_file in compose_files:
        compose_prefix.extend(["-f", compose_file])
    adapter = ComposeLifecycleAdapter(compose_prefix=compose_prefix)
    requested = ResourcePolicy(args.policy)
    usable_mb = adapter.usable_gpu_memory_mb()
    budget = MemoryBudget(
        usable_mb=usable_mb,
        reserve_mb=int(os.getenv("AGENT_SPEAK_RESOURCE_RESERVE_MB", "1500")),
        asr_mb=int(os.getenv("AGENT_SPEAK_RESOURCE_ASR_BUDGET_MB", "6500")),
        correction_mb=int(
            os.getenv("AGENT_SPEAK_RESOURCE_CORRECTION_BUDGET_MB", "1000")
        ),
        tts_mb=int(os.getenv("AGENT_SPEAK_RESOURCE_TTS_BUDGET_MB", "9500")),
    )
    resolved = resolve_policy(requested, budget)
    asr_ready = adapter.is_ready(Workload.ASR)
    tts_ready = adapter.is_ready(Workload.TTS)
    profile = (
        ResourceProfile.TTS_ONLY
        if tts_ready and not asr_ready
        else ResourceProfile.ASR_ONLY
    )
    desired = frozenset(plan_profile(profile))
    snapshot = ResourceSnapshot(
        requested_policy=requested,
        resolved_policy=resolved,
        profile=profile,
        desired_workloads=desired,
        workloads={
            workload: ResourceSupervisor._observed_status(
                adapter,
                workload,
                desired=workload in desired,
            )
            for workload in Workload
        },
        operation=None,
        last_ready_profile=None,
    )
    state_path = args.state or args.socket.with_name("state.json")
    supervisor = ResourceSupervisor(
        lifecycle=adapter,
        store=ResourceStateStore(state_path),
        snapshot=snapshot,
        start_timeout=float(
            os.getenv("AGENT_SPEAK_RESOURCE_START_TIMEOUT_SECONDS", "300")
        ),
    )
    ResourceUnixServer(args.socket, supervisor).serve_forever()


if __name__ == "__main__":
    main()
