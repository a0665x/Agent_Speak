from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AI_Avatar.tools.avatar_motion.models import load_motion, load_rig
from AI_Avatar.tools.avatar_motion.pose import render_pose_map, save_png


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render deterministic skeleton pose maps."
    )
    parser.add_argument("--rig", type=Path, required=True)
    parser.add_argument("--motion", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    rig = load_rig(args.rig)
    motion = load_motion(args.motion, rig)
    for pose in motion.poses:
        path = args.output / f"{pose.frame:03d}_{pose.id}.png"
        save_png(render_pose_map(rig, pose), path)
    print(f"POSE_MAPS_READY count={len(motion.poses)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

