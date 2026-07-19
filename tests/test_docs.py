from pathlib import Path
import re

from agent_speak.app import create_app
from agent_speak.config import Settings


ROOT = Path(__file__).resolve().parents[1]
QUICKSTART = ROOT / "docs" / "OPENAPI_QUICKSTART_ZH_TW.md"


def test_openapi_quickstart_only_references_real_operations(tmp_path: Path) -> None:
    document = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime")
    ).openapi()
    text = QUICKSTART.read_text(encoding="utf-8")
    operations = re.findall(r"`(GET|POST|PATCH|DELETE) (/api/v1/[^`]+)`", text)

    assert operations, "quickstart must identify its documented OpenAPI operations"
    for method, path in operations:
        assert path in document["paths"], f"documented path is missing from OpenAPI: {path}"
        assert method.lower() in document["paths"][path], (
            f"documented method is missing from OpenAPI: {method} {path}"
        )


def test_public_readme_and_agent_entrypoint_are_clone_ready() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agent_entrypoint = ROOT / "AGENTS.md"

    assert "git clone https://github.com/a0665x/Agent_Speak.git" in readme
    assert "<repository-url>" not in readme
    assert agent_entrypoint.is_file()
    assert "spec/PROJECT_MAP.md" in agent_entrypoint.read_text(encoding="utf-8")
    assert "skills/agent-speak/SKILL.md" in agent_entrypoint.read_text(encoding="utf-8")


def test_portable_skill_has_valid_frontmatter_and_mcp_entrypoint() -> None:
    skill = (ROOT / "skills" / "agent-speak" / "SKILL.md").read_text(encoding="utf-8")

    assert skill.startswith("---\n")
    frontmatter = skill.split("---\n", 2)[1]
    assert "name: agent-speak" in frontmatter
    assert "description:" in frontmatter
    assert "version:" in frontmatter
    assert "license: MIT" in frontmatter
    assert (ROOT / "LICENSE").is_file()
    entrypoint = (ROOT / "scripts" / "run_mcp.sh")
    assert entrypoint.stat().st_mode & 0o111
    assert 'source "$ROOT_DIR/.env"' not in entrypoint.read_text(encoding="utf-8")


def test_public_ignore_rules_cover_local_agent_state_and_common_secrets() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for rule in (
        ".codex/", ".agent/", ".agents/", ".env.*", "!.env.example", ".netrc", "id_rsa",
        "*credentials*.yml", "*secret*.yaml",
    ):
        assert rule in ignore


def test_openapi_quickstart_relative_markdown_links_exist() -> None:
    files = (
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "spec" / "PROJECT_MAP.md",
        ROOT / "spec" / "API.md",
        ROOT / "spec" / "SKILL_AND_MCP.md",
        QUICKSTART,
    )

    for source in files:
        text = source.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            path = (source.parent / target.split("#", 1)[0]).resolve()
            assert path.exists(), f"broken Markdown link in {source}: {target}"
