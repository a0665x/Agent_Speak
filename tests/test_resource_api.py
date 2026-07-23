from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import httpx
import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings
from agent_speak.errors import PlatformError
from agent_speak.resource_control import ResourceControlClient
from agent_speak.resource_types import (
    OperationPhase,
    ResourceOperation,
    ResourcePolicy,
    ResourceProfile,
    ResourceSnapshot,
    Workload,
)


def ready_asr_snapshot() -> ResourceSnapshot:
    return ResourceSnapshot.initial(
        requested_policy=ResourcePolicy.AUTO,
        resolved_policy=ResourcePolicy.EXCLUSIVE,
        profile=ResourceProfile.ASR_ONLY,
    )


def ready_operation(
    *,
    action: str = "reconcile",
    target: str = "tts_only",
) -> ResourceOperation:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return ResourceOperation(
        id="op_0123456789abcdef",
        action=action,  # type: ignore[arg-type]
        target=target,
        phase=OperationPhase.READY,
        created_at=now,
        updated_at=now,
    )


class FakeResourceControl:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.current = ready_operation()

    def snapshot(self) -> ResourceSnapshot:
        return ready_asr_snapshot()

    def reconcile(self, profile: ResourceProfile) -> ResourceOperation:
        self.calls.append(("reconcile", profile.value))
        return self.current

    def reset(self, workload: Workload) -> ResourceOperation:
        self.calls.append(("reset", workload.value))
        return ready_operation(action="reset", target=workload.value)

    def operation(self, operation_id: str) -> ResourceOperation:
        self.calls.append(("operation", operation_id))
        return self.current


class UnavailableResourceControl(FakeResourceControl):
    def snapshot(self) -> ResourceSnapshot:
        raise PlatformError(
            "resource_supervisor_unavailable",
            "Resource supervisor is unavailable",
            status_code=503,
            stage="resources",
            retryable=True,
            details={"operator_hint": "./run.sh --status"},
        )


@pytest.mark.anyio
async def test_resource_api_returns_snapshot_and_accepts_profile(
    tmp_path: Path,
) -> None:
    control = FakeResourceControl()
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            runtime_dir=tmp_path / "runtime",
        ),
        resource_control=control,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        current = await client.get("/api/v1/resources")
        accepted = await client.post(
            "/api/v1/resources/reconcile",
            json={"profile": "tts_only"},
        )
        reset = await client.post("/api/v1/resources/tts/reset")
        operation = await client.get(
            "/api/v1/resource-operations/op_0123456789abcdef"
        )

    assert current.status_code == 200
    assert current.json()["resolved_policy"] == "exclusive"
    assert accepted.status_code == 202
    assert reset.status_code == 202
    assert operation.status_code == 200
    assert control.calls == [
        ("reconcile", "tts_only"),
        ("reset", "tts"),
        ("operation", "op_0123456789abcdef"),
    ]


@pytest.mark.anyio
async def test_resource_api_validates_values_and_maps_missing_supervisor(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            runtime_dir=tmp_path / "runtime",
        ),
        resource_control=UnavailableResourceControl(),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        invalid_profile = await client.post(
            "/api/v1/resources/reconcile",
            json={"profile": "shell"},
        )
        invalid_workload = await client.post(
            "/api/v1/resources/shell/reset"
        )
        invalid_operation = await client.get(
            "/api/v1/resource-operations/../../bad"
        )
        unavailable = await client.get("/api/v1/resources")

    assert invalid_profile.status_code == 422
    assert invalid_workload.status_code == 422
    assert invalid_operation.status_code in {404, 422}
    assert unavailable.status_code == 503
    assert unavailable.json()["error"] == {
        "code": "resource_supervisor_unavailable",
        "message": "Resource supervisor is unavailable",
        "stage": "resources",
        "retryable": True,
        "details": {"operator_hint": "./run.sh --status"},
    }


class FakeSocket:
    def __init__(
        self,
        response: bytes = b"",
        *,
        connect_error: OSError | None = None,
    ) -> None:
        self.response = response
        self.connect_error = connect_error
        self.sent = b""

    def __enter__(self) -> "FakeSocket":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def settimeout(self, _: float) -> None:
        return None

    def connect(self, _: str) -> None:
        if self.connect_error is not None:
            raise self.connect_error

    def sendall(self, payload: bytes) -> None:
        self.sent = payload

    def makefile(self, _: str) -> "FakeSocket":
        return self

    def readline(self, _: int) -> bytes:
        return self.response


def test_resource_control_accepts_only_bounded_typed_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = {
        "ok": True,
        "result": ready_asr_snapshot().to_dict(),
    }
    fake = FakeSocket(
        json.dumps(payload, separators=(",", ":")).encode() + b"\n"
    )
    monkeypatch.setattr(
        "agent_speak.resource_control.socket.socket",
        lambda *_: fake,
    )
    client = ResourceControlClient(tmp_path / "control.sock")

    result = client.snapshot()

    assert result.resolved_policy is ResourcePolicy.EXCLUSIVE
    assert json.loads(fake.sent) == {"action": "snapshot"}


@pytest.mark.parametrize(
    "response",
    [
        b"not-json\n",
        b'{"ok":true,"result":{}}\n',
        b"x" * (64 * 1024 + 1),
        b'{"ok":false,"error":{"code":"private /secret","retryable":false}}\n',
    ],
)
def test_resource_control_redacts_invalid_or_oversized_responses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    response: bytes,
) -> None:
    monkeypatch.setattr(
        "agent_speak.resource_control.socket.socket",
        lambda *_: FakeSocket(response),
    )
    client = ResourceControlClient(tmp_path / "control.sock")

    with pytest.raises(PlatformError) as raised:
        client.snapshot()

    assert raised.value.code == "resource_supervisor_unavailable"
    assert "/secret" not in raised.value.message


def test_resource_control_maps_socket_failure_without_raw_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "agent_speak.resource_control.socket.socket",
        lambda *_: FakeSocket(
            connect_error=OSError("private socket failure /secret")
        ),
    )
    client = ResourceControlClient(tmp_path / "control.sock")

    with pytest.raises(PlatformError) as raised:
        client.snapshot()

    assert raised.value.code == "resource_supervisor_unavailable"
    assert raised.value.status_code == 503
    assert "/secret" not in raised.value.message
