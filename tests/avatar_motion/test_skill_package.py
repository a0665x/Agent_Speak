from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = (
    ROOT / "AI_Avatar/assets/skills/generate-character-motion"
)
SKILL = SKILL_ROOT / "SKILL.md"


def test_skill_names_capability_and_publication_boundaries() -> None:
    text = SKILL.read_text(encoding="utf-8")

    for phrase in (
        "not ControlNet",
        "one keyframe",
        "human approval",
        "ignored candidate",
        "never log credentials",
        "shared S0",
        "no publication authority",
    ):
        assert phrase in text


def test_skill_has_discovery_metadata() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert text.startswith("---\nname: generate-character-motion\n")
    assert "description: Use when" in text
    assert (SKILL_ROOT / "agents/openai.yaml").is_file()


def test_skill_scripts_support_help() -> None:
    scripts = sorted((SKILL_ROOT / "scripts").glob("*.py"))

    assert {path.name for path in scripts} >= {
        "init_motion_job.py",
        "render_pose_maps.py",
        "validate_motion_job.py",
    }
    for script in scripts:
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
