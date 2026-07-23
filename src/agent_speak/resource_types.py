"""Pure resource-policy and workload profile types."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum


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
