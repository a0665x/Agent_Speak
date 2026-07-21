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


def test_codex_voice_recorder_is_documented() -> None:
    ui = (ROOT / "spec" / "UI.md").read_text(encoding="utf-8")
    testing = (ROOT / "spec" / "TESTING.md").read_text(encoding="utf-8")

    assert "`/codex`" in ui
    assert "Zone Vibe 100" in ui
    assert "clipboard" in ui.lower()
    assert "Codex CLI" in testing
    assert "physical playback" in testing


def test_realtime_studio_contract_is_documented_without_agent_claims() -> None:
    texts = [
        (ROOT / "README.md").read_text(encoding="utf-8"),
        (ROOT / "README.zh-TW.md").read_text(encoding="utf-8"),
        (ROOT / "spec" / "UI.md").read_text(encoding="utf-8"),
    ]
    combined = "\n".join(texts)
    for phrase in (
        "/realtime",
        "Zone Vibe 100",
        "900",
        "1,800",
        "WebSocket",
        "Qwen",
        "partial",
        "previous sentence",
        "不會自動重連",
        "physical playback",
    ):
        assert phrase in combined
    assert "continuous transcription only" in texts[0]
    assert "只做持續轉錄" in texts[1]


def test_multilingual_ui_and_openapi_contract_is_documented() -> None:
    ui = (ROOT / "spec" / "UI.md").read_text(encoding="utf-8")
    api = (ROOT / "spec" / "API.md").read_text(encoding="utf-8")
    testing = (ROOT / "spec" / "TESTING.md").read_text(encoding="utf-8")
    project_map = (ROOT / "spec" / "PROJECT_MAP.md").read_text(encoding="utf-8")
    combined = "\n".join((ui, api, testing, project_map))

    for locale in ("en", "zh-TW", "ja", "ko"):
        assert f"`{locale}`" in combined
    assert "English is the default" in ui
    assert "query parameter → localStorage → English" in ui
    assert "`/docs?lang=`" in api
    assert "`/openapi.json?lang=`" in api
    assert "API paths, operation IDs, schema names, property names, and payloads do not change" in api
    assert "must not request microphone permission" in testing


def test_readme_capture_script_is_safe_and_covers_every_product_layer() -> None:
    script = (ROOT / "scripts" / "capture_readme_screenshots.sh").read_text(encoding="utf-8")

    for artifact in (
        "01-project-home-hero.png",
        "02-project-home-destinations.png",
        "03-project-home-pipeline.png",
        "04-asr-realtime-device-gate.png",
        "05-asr-realtime-process-cycle.png",
        "06-asr-realtime-transcript.png",
        "07-asr-realtime-utterance-graph.png",
        "08-api-explorer.png",
        "agent-speak-tour.gif",
    ):
        assert artifact in script
    assert "?lang=en" in script
    assert "use-fake-ui-for-media-stream" not in script
    assert "getUserMedia" not in script
    assert "click()" not in script
