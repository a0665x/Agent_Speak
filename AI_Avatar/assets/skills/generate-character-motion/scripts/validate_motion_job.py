from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AI_Avatar.tools.avatar_motion.job import MotionJobStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate hash-bound approvals in an avatar motion job."
    )
    parser.add_argument("--job", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    store = MotionJobStore.load(args.job)
    approvals = store.valid_approvals()
    next_pose = store.unlocked_pose_id or "complete"
    print(
        f"MOTION_JOB_VALID approvals={len(approvals)} "
        f"next_pose={next_pose}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
