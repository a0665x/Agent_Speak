"""Pure resource-policy and workload profile types."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
import re
from typing import Any, Literal


class ResourcePolicy(str, Enum):
    AUTO = "auto"
    EXCLUSIVE = "exclusive"
    CONCURRENT = "concurrent"
    MULTI_GPU = "multi_gpu"


class ResourceProfile(str, Enum):
    ASR_ONLY = "asr_only"
    TTS_ONLY = "tts_only"
    FULL_PIPELINE = "full_pipeline"


class Workload(str, Enum):
    ASR = "asr"
    CORRECTION = "correction"
    AGENT = "agent"
    TTS = "tts"


class OperationPhase(str, Enum):
    QUEUED = "queued"
    DRAINING = "draining"
    RELEASING = "releasing"
    STARTING = "starting"
    WARMING = "warming"
    READY = "ready"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class WorkloadLifecycle(str, Enum):
    STOPPED = "stopped"
    DRAINING = "draining"
    STARTING = "starting"
    WARMING = "warming"
    READY = "ready"
    FAILED = "failed"


OPERATION_ID_RE = re.compile(r"^op_[0-9a-f]{16,32}$")
STABLE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    *,
    kind: str,
) -> None:
    if set(value) != expected:
        raise ValueError(f"invalid {kind} fields")


def _bounded_optional(
    value: object,
    *,
    name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ValueError(f"invalid {name}")
    if "\n" in value or "\r" in value:
        raise ValueError(f"invalid {name}")
    return value


@dataclass(frozen=True, slots=True)
class MemoryBudget:
    usable_mb: int
    reserve_mb: int
    asr_mb: int
    correction_mb: int
    tts_mb: int

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{item.name} must be a positive integer")

    @property
    def concurrent_required_mb(self) -> int:
        return (
            self.reserve_mb
            + self.asr_mb
            + self.correction_mb
            + self.tts_mb
        )


PROFILE_WORKLOADS: dict[ResourceProfile, frozenset[Workload]] = {
    ResourceProfile.ASR_ONLY: frozenset(
        {Workload.ASR, Workload.CORRECTION}
    ),
    ResourceProfile.TTS_ONLY: frozenset({Workload.TTS}),
    ResourceProfile.FULL_PIPELINE: frozenset(
        {
            Workload.ASR,
            Workload.CORRECTION,
            Workload.AGENT,
            Workload.TTS,
        }
    ),
}


def resolve_policy(
    requested: ResourcePolicy,
    budget: MemoryBudget,
) -> ResourcePolicy:
    if requested is not ResourcePolicy.AUTO:
        return requested
    if budget.usable_mb >= budget.concurrent_required_mb:
        return ResourcePolicy.CONCURRENT
    return ResourcePolicy.EXCLUSIVE


def plan_profile(profile: ResourceProfile) -> set[Workload]:
    return set(PROFILE_WORKLOADS[profile])


@dataclass(frozen=True, slots=True)
class WorkloadStatus:
    workload: Workload
    desired: bool
    lifecycle: WorkloadLifecycle
    ready: bool
    model: str | None = None
    device: str = "unavailable"
    error_code: str | None = None
    operator_hint: str | None = None

    def __post_init__(self) -> None:
        if self.ready != (self.lifecycle is WorkloadLifecycle.READY):
            raise ValueError("ready must match workload lifecycle")
        _bounded_optional(self.model, name="model", max_length=128)
        _bounded_optional(self.device, name="device", max_length=64)
        if self.error_code is not None and not STABLE_CODE_RE.fullmatch(
            self.error_code
        ):
            raise ValueError("invalid workload error_code")
        _bounded_optional(
            self.operator_hint,
            name="operator_hint",
            max_length=256,
        )

    @classmethod
    def stopped(
        cls,
        workload: Workload,
        *,
        desired: bool = False,
    ) -> "WorkloadStatus":
        return cls(
            workload=workload,
            desired=desired,
            lifecycle=WorkloadLifecycle.STOPPED,
            ready=False,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "workload": self.workload.value,
            "desired": self.desired,
            "lifecycle": self.lifecycle.value,
            "ready": self.ready,
            "model": self.model,
            "device": self.device,
            "error_code": self.error_code,
            "operator_hint": self.operator_hint,
        }

    @classmethod
    def from_dict(cls, value: object) -> "WorkloadStatus":
        if not isinstance(value, dict):
            raise ValueError("invalid workload status")
        _require_exact_keys(
            value,
            {
                "workload",
                "desired",
                "lifecycle",
                "ready",
                "model",
                "device",
                "error_code",
                "operator_hint",
            },
            kind="workload status",
        )
        if not isinstance(value["desired"], bool) or not isinstance(
            value["ready"], bool
        ):
            raise ValueError("invalid workload status flags")
        return cls(
            workload=Workload(value["workload"]),
            desired=value["desired"],
            lifecycle=WorkloadLifecycle(value["lifecycle"]),
            ready=value["ready"],
            model=_bounded_optional(
                value["model"],
                name="model",
                max_length=128,
            ),
            device=_bounded_optional(
                value["device"],
                name="device",
                max_length=64,
            )
            or "unavailable",
            error_code=_bounded_optional(
                value["error_code"],
                name="error_code",
                max_length=64,
            ),
            operator_hint=_bounded_optional(
                value["operator_hint"],
                name="operator_hint",
                max_length=256,
            ),
        )


@dataclass(frozen=True, slots=True)
class ResourceOperation:
    id: str
    action: Literal["reconcile", "reset"]
    target: str
    phase: OperationPhase
    created_at: str
    updated_at: str
    error_code: str | None = None
    operator_hint: str | None = None

    def __post_init__(self) -> None:
        if not OPERATION_ID_RE.fullmatch(self.id):
            raise ValueError("invalid operation id")
        if self.action not in {"reconcile", "reset"}:
            raise ValueError("invalid operation action")
        allowed_targets = {
            *(item.value for item in ResourceProfile),
            *(item.value for item in Workload),
        }
        if self.target not in allowed_targets:
            raise ValueError("invalid operation target")
        for name, value in (
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid {name}") from exc
        if self.error_code is not None and not STABLE_CODE_RE.fullmatch(
            self.error_code
        ):
            raise ValueError("invalid operation error_code")
        _bounded_optional(
            self.operator_hint,
            name="operator_hint",
            max_length=256,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "action": self.action,
            "target": self.target,
            "phase": self.phase.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error_code": self.error_code,
            "operator_hint": self.operator_hint,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ResourceOperation":
        if not isinstance(value, dict):
            raise ValueError("invalid resource operation")
        _require_exact_keys(
            value,
            {
                "id",
                "action",
                "target",
                "phase",
                "created_at",
                "updated_at",
                "error_code",
                "operator_hint",
            },
            kind="resource operation",
        )
        if not all(
            isinstance(value[name], str)
            for name in (
                "id",
                "action",
                "target",
                "phase",
                "created_at",
                "updated_at",
            )
        ):
            raise ValueError("invalid resource operation values")
        return cls(
            id=value["id"],
            action=value["action"],
            target=value["target"],
            phase=OperationPhase(value["phase"]),
            created_at=value["created_at"],
            updated_at=value["updated_at"],
            error_code=_bounded_optional(
                value["error_code"],
                name="error_code",
                max_length=64,
            ),
            operator_hint=_bounded_optional(
                value["operator_hint"],
                name="operator_hint",
                max_length=256,
            ),
        )


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    requested_policy: ResourcePolicy
    resolved_policy: ResourcePolicy
    profile: ResourceProfile | None
    desired_workloads: frozenset[Workload]
    workloads: dict[Workload, WorkloadStatus]
    operation: ResourceOperation | None
    last_ready_profile: ResourceProfile | None

    def __post_init__(self) -> None:
        if set(self.workloads) != set(Workload):
            raise ValueError("snapshot must contain every workload")
        for workload, status in self.workloads.items():
            if workload is not status.workload:
                raise ValueError("workload status key mismatch")
            if status.desired != (workload in self.desired_workloads):
                raise ValueError("desired workload status mismatch")

    @classmethod
    def initial(
        cls,
        *,
        requested_policy: ResourcePolicy,
        resolved_policy: ResourcePolicy,
        profile: ResourceProfile,
    ) -> "ResourceSnapshot":
        desired = frozenset(plan_profile(profile))
        return cls(
            requested_policy=requested_policy,
            resolved_policy=resolved_policy,
            profile=profile,
            desired_workloads=desired,
            workloads={
                workload: WorkloadStatus.stopped(
                    workload,
                    desired=workload in desired,
                )
                for workload in Workload
            },
            operation=None,
            last_ready_profile=None,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy": self.requested_policy.value,
            "resolved_policy": self.resolved_policy.value,
            "profile": self.profile.value if self.profile is not None else None,
            "desired_workloads": sorted(
                workload.value for workload in self.desired_workloads
            ),
            "workloads": {
                workload.value: self.workloads[workload].to_dict()
                for workload in Workload
            },
            "operation": (
                self.operation.to_dict() if self.operation is not None else None
            ),
            "last_ready_profile": (
                self.last_ready_profile.value
                if self.last_ready_profile is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "ResourceSnapshot":
        if not isinstance(value, dict):
            raise ValueError("invalid resource snapshot")
        _require_exact_keys(
            value,
            {
                "requested_policy",
                "resolved_policy",
                "profile",
                "desired_workloads",
                "workloads",
                "operation",
                "last_ready_profile",
            },
            kind="resource snapshot",
        )
        desired_value = value["desired_workloads"]
        workloads_value = value["workloads"]
        if not isinstance(desired_value, list) or not isinstance(
            workloads_value, dict
        ):
            raise ValueError("invalid resource snapshot collections")
        desired = frozenset(Workload(item) for item in desired_value)
        if set(workloads_value) != {item.value for item in Workload}:
            raise ValueError("invalid resource workload keys")
        last_ready = value["last_ready_profile"]
        if last_ready is not None and not isinstance(last_ready, str):
            raise ValueError("invalid last_ready_profile")
        profile_value = value["profile"]
        if profile_value is not None and not isinstance(profile_value, str):
            raise ValueError("invalid profile")
        return cls(
            requested_policy=ResourcePolicy(value["requested_policy"]),
            resolved_policy=ResourcePolicy(value["resolved_policy"]),
            profile=(
                ResourceProfile(profile_value)
                if profile_value is not None
                else None
            ),
            desired_workloads=desired,
            workloads={
                workload: WorkloadStatus.from_dict(
                    workloads_value[workload.value]
                )
                for workload in Workload
            },
            operation=(
                ResourceOperation.from_dict(value["operation"])
                if value["operation"] is not None
                else None
            ),
            last_ready_profile=(
                ResourceProfile(last_ready) if last_ready is not None else None
            ),
        )
