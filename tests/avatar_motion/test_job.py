from __future__ import annotations

from pathlib import Path

import pytest

from AI_Avatar.tools.avatar_motion.job import MotionJobStore, init_job


def _write(path: Path, value: str) -> Path:
    path.write_text(value, encoding="utf-8")
    return path


def _new_job(tmp_path: Path, *, character_id: str = "henry") -> MotionJobStore:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    return init_job(
        candidate_root=tmp_path / "candidates",
        character_id=character_id,
        motion_id="scratch_head",
        job_id="run_001",
        reference_path=_write(inputs / "reference.png", "reference"),
        s0_path=_write(inputs / "s0.png", "s0"),
        rig_path=_write(inputs / "rig.json", "rig"),
        motion_path=_write(inputs / "motion.json", "motion"),
        pose_ids=("anticipation", "lift", "contact"),
    )


def test_job_root_stays_below_candidates(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="safe identifier"):
        _new_job(tmp_path, character_id="../../escape")


def test_only_first_pose_is_unlocked_initially(tmp_path: Path) -> None:
    job = _new_job(tmp_path)

    assert job.unlocked_pose_id == "anticipation"
    assert job.valid_approvals() == ()


def test_approval_unlocks_exactly_one_next_pose(tmp_path: Path) -> None:
    job = _new_job(tmp_path)
    candidate = _write(job.root / "candidate.png", "candidate")
    prompt = _write(job.root / "prompt.json", "prompt")

    job.approve_pose(
        "anticipation",
        candidate_path=candidate,
        prompt_path=prompt,
        automatic_gates="passed",
        human_decision="approved",
    )

    assert job.unlocked_pose_id == "lift"
    assert tuple(item.pose_id for item in job.valid_approvals()) == (
        "anticipation",
    )


def test_approval_hash_change_invalidates_downstream(tmp_path: Path) -> None:
    job = _new_job(tmp_path)
    candidate = _write(job.root / "candidate.png", "candidate")
    prompt = _write(job.root / "prompt.json", "prompt")
    job.approve_pose(
        "anticipation",
        candidate_path=candidate,
        prompt_path=prompt,
        automatic_gates="passed",
        human_decision="approved",
    )
    job.resolve_input("motion").write_text(
        "changed motion",
        encoding="utf-8",
    )

    resumed = MotionJobStore.load(job.job_path)

    assert resumed.valid_approvals() == ()
    assert resumed.unlocked_pose_id == "anticipation"


def test_automatic_failure_cannot_be_human_approved(tmp_path: Path) -> None:
    job = _new_job(tmp_path)

    with pytest.raises(ValueError, match="automatic gates"):
        job.approve_pose(
            "anticipation",
            candidate_path=_write(job.root / "candidate.png", "candidate"),
            prompt_path=_write(job.root / "prompt.json", "prompt"),
            automatic_gates="failed",
            human_decision="approved",
        )
