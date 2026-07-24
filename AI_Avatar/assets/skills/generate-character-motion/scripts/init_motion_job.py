from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AI_Avatar.tools.avatar_motion.job import init_job
from AI_Avatar.tools.avatar_motion.models import load_motion, load_rig


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize an ignored, stage-gated avatar motion job."
    )
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--s0", type=Path, required=True)
    parser.add_argument("--rig", type=Path, required=True)
    parser.add_argument("--motion", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=PROJECT_ROOT / "AI_Avatar/.candidates",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    rig = load_rig(args.rig)
    motion = load_motion(args.motion, rig)
    pose_ids = tuple(pose.id for pose in motion.poses if pose.id != "s0")
    job = init_job(
        candidate_root=args.candidates,
        character_id=rig.character_id,
        motion_id=motion.motion_id,
        job_id=args.job_id,
        reference_path=args.reference,
        s0_path=args.s0,
        rig_path=args.rig,
        motion_path=args.motion,
        pose_ids=pose_ids,
    )
    print(f"MOTION_JOB_READY job={job.job_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
