from __future__ import annotations

from agent_speak.resource_types import (
    MemoryBudget,
    ResourcePolicy,
    ResourceProfile,
    Workload,
    plan_profile,
    resolve_policy,
)


def test_auto_uses_exclusive_when_combined_budget_does_not_fit() -> None:
    budget = MemoryBudget(
        usable_mb=11_000,
        reserve_mb=1_500,
        asr_mb=6_500,
        correction_mb=1_000,
        tts_mb=9_500,
    )

    assert resolve_policy(ResourcePolicy.AUTO, budget) is ResourcePolicy.EXCLUSIVE


def test_auto_uses_concurrent_when_all_inference_budgets_fit() -> None:
    budget = MemoryBudget(
        usable_mb=48_000,
        reserve_mb=2_000,
        asr_mb=6_500,
        correction_mb=1_000,
        tts_mb=9_500,
    )

    assert resolve_policy(ResourcePolicy.AUTO, budget) is ResourcePolicy.CONCURRENT


def test_explicit_policy_is_never_silently_changed() -> None:
    budget = MemoryBudget(
        usable_mb=11_000,
        reserve_mb=1_500,
        asr_mb=6_500,
        correction_mb=1_000,
        tts_mb=9_500,
    )

    assert (
        resolve_policy(ResourcePolicy.CONCURRENT, budget)
        is ResourcePolicy.CONCURRENT
    )


def test_profiles_are_declarative_and_full_pipeline_reserves_agent() -> None:
    assert plan_profile(ResourceProfile.ASR_ONLY) == {
        Workload.ASR,
        Workload.CORRECTION,
    }
    assert plan_profile(ResourceProfile.TTS_ONLY) == {Workload.TTS}
    assert plan_profile(ResourceProfile.FULL_PIPELINE) == {
        Workload.ASR,
        Workload.CORRECTION,
        Workload.AGENT,
        Workload.TTS,
    }


def test_memory_budget_rejects_non_positive_values() -> None:
    try:
        MemoryBudget(
            usable_mb=0,
            reserve_mb=1_500,
            asr_mb=6_500,
            correction_mb=1_000,
            tts_mb=9_500,
        )
    except ValueError as exc:
        assert "usable_mb" in str(exc)
    else:
        raise AssertionError("zero usable memory must be rejected")
