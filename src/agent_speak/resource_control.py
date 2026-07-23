"""Bounded Gateway client for the host-owned resource supervisor."""

from __future__ import annotations

import json
from pathlib import Path
import socket

from .errors import PlatformError
from .resource_types import (
    ResourceOperation,
    ResourceProfile,
    ResourceSnapshot,
    STABLE_CODE_RE,
    Workload,
)


MAX_RESOURCE_RESPONSE_BYTES = 64 * 1024


def _unavailable() -> PlatformError:
    return PlatformError(
        "resource_supervisor_unavailable",
        "Resource supervisor is unavailable",
        status_code=503,
        stage="resources",
        retryable=True,
        details={"operator_hint": "./run.sh --status"},
    )


class ResourceControlClient:
    def __init__(
        self,
        socket_path: Path,
        *,
        timeout: float = 5.0,
    ) -> None:
        self.socket_path = socket_path
        self.timeout = timeout

    def _request(self, request: dict[str, object]) -> object:
        encoded = (
            json.dumps(request, separators=(",", ":")).encode("utf-8")
            + b"\n"
        )
        try:
            with socket.socket(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
            ) as client:
                client.settimeout(self.timeout)
                client.connect(str(self.socket_path))
                client.sendall(encoded)
                response = client.makefile("rb").readline(
                    MAX_RESOURCE_RESPONSE_BYTES + 1
                )
            if (
                not response.endswith(b"\n")
                or len(response) > MAX_RESOURCE_RESPONSE_BYTES
            ):
                raise ValueError("invalid resource response framing")
            payload = json.loads(response)
            if not isinstance(payload, dict):
                raise ValueError("invalid resource response")
            if set(payload) == {"ok", "result"} and payload["ok"] is True:
                return payload["result"]
            if set(payload) == {"ok", "error"} and payload["ok"] is False:
                self._raise_supervisor_error(payload["error"])
            raise ValueError("invalid resource response envelope")
        except PlatformError:
            raise
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise _unavailable() from exc

    @staticmethod
    def _raise_supervisor_error(error: object) -> None:
        if not isinstance(error, dict) or set(error) != {
            "code",
            "retryable",
        }:
            raise ValueError("invalid resource error")
        code = error["code"]
        retryable = error["retryable"]
        if (
            not isinstance(code, str)
            or not STABLE_CODE_RE.fullmatch(code)
            or not isinstance(retryable, bool)
        ):
            raise ValueError("invalid resource error")
        if code == "resource_operation_not_found":
            raise PlatformError(
                code,
                "Resource operation was not found",
                status_code=404,
                stage="resources",
            )
        if code == "agent_provider_unavailable":
            raise PlatformError(
                code,
                "A production Agent provider is not available",
                status_code=409,
                stage="resources",
            )
        raise _unavailable()

    def snapshot(self) -> ResourceSnapshot:
        try:
            return ResourceSnapshot.from_dict(
                self._request({"action": "snapshot"})
            )
        except PlatformError:
            raise
        except ValueError as exc:
            raise _unavailable() from exc

    def reconcile(self, profile: ResourceProfile) -> ResourceOperation:
        try:
            return ResourceOperation.from_dict(
                self._request(
                    {
                        "action": "reconcile",
                        "profile": profile.value,
                    }
                )
            )
        except PlatformError:
            raise
        except ValueError as exc:
            raise _unavailable() from exc

    def reset(self, workload: Workload) -> ResourceOperation:
        try:
            return ResourceOperation.from_dict(
                self._request(
                    {
                        "action": "reset",
                        "workload": workload.value,
                    }
                )
            )
        except PlatformError:
            raise
        except ValueError as exc:
            raise _unavailable() from exc

    def operation(self, operation_id: str) -> ResourceOperation:
        try:
            return ResourceOperation.from_dict(
                self._request(
                    {
                        "action": "operation",
                        "operation_id": operation_id,
                    }
                )
            )
        except PlatformError:
            raise
        except ValueError as exc:
            raise _unavailable() from exc
