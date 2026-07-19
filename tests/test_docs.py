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


def test_openapi_quickstart_relative_markdown_links_exist() -> None:
    files = (
        ROOT / "README.md",
        ROOT / "spec" / "PROJECT_MAP.md",
        ROOT / "spec" / "API.md",
        QUICKSTART,
    )

    for source in files:
        text = source.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            path = (source.parent / target.split("#", 1)[0]).resolve()
            assert path.exists(), f"broken Markdown link in {source}: {target}"
