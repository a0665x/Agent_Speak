from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_docker_first_files_and_audio_mapping_exist() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    gateway = compose["services"]["gateway"]
    assert gateway["build"]["context"] == "."
    assert gateway["devices"] == ["/dev/snd:/dev/snd"]
    assert gateway["ports"] == ["${AGENT_SPEAK_PUBLISH_HOST:-127.0.0.1}:${AGENT_SPEAK_PORT:-8765}:8765"]
    assert gateway["healthcheck"]["test"]
    assert gateway["restart"] == "unless-stopped"
    assert "${AGENT_SPEAK_DATA_PATH:-./data}:/app/data" in gateway["volumes"]
    assert "${AGENT_SPEAK_RUNTIME_PATH:-./runtime}:/app/runtime" in gateway["volumes"]
    assert "${AGENT_SPEAK_MODELS_PATH:-./models}:/app/models" in gateway["volumes"]
    assert "alsa-utils" in dockerfile
    assert "COPY . ." in dockerfile
    assert "HEALTHCHECK" in dockerfile
    for private_path in (
        ".env", ".venv", "data", "runtime", "models", ".codex", ".agent", ".hermes",
        "*.pem", "*.key", "*.p12", "*credentials*.json", "*secret*.yaml", ".netrc", "id_rsa",
    ):
        assert private_path in ignore
    test_service = compose["services"]["gateway-test"]
    assert "devices" not in test_service
    assert "volumes" not in test_service
    assert test_service["profiles"] == ["test"]


def test_root_run_script_exposes_single_docker_operator_interface() -> None:
    script = ROOT / "run.sh"
    source = script.read_text(encoding="utf-8")
    assert os.access(script, os.X_OK)
    subprocess.run(["bash", "-n", str(script)], check=True)

    help_result = subprocess.run([str(script), "--help"], cwd=ROOT, capture_output=True, text=True, check=True)
    for option in ("--build", "--up", "--down", "--down_up", "--restart", "--rebuild", "--status", "--logs", "--test", "--help"):
        assert option in help_result.stdout
    assert "docker compose" in source
    assert "/dev/snd/controlC*" in source
    assert "ps --all -q gateway" in source
    assert "arecord -l" in source and "aplay -l" in source
    assert "gateway-test" in source
    assert ".venv" not in source


def test_run_script_dispatches_expected_compose_commands(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "docker.log"
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n"
        "if [[ \"$1 $2\" == 'compose ps' ]]; then echo 'fake-container'; fi\n"
        "if [[ \"$1\" == 'inspect' ]]; then echo 'healthy'; fi\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}", "FAKE_DOCKER_LOG": str(log)}

    expectations = {
        "--build": ("compose build", "compose up -d"),
        "--up": ("compose up -d",),
        "--down": ("compose down",),
        "--down_up": ("compose down", "compose up -d"),
        "--restart": ("compose down", "compose up -d"),
        "--rebuild": ("compose down", "compose build --no-cache", "compose up -d"),
        "--status": ("compose ps",),
        "--logs": ("compose logs --tail",),
        "--test": ("compose run --rm --no-deps", "gateway-test"),
    }
    for option, fragments in expectations.items():
        log.write_text("", encoding="utf-8")
        result = subprocess.run([str(ROOT / "run.sh"), option], cwd=ROOT, env=env, capture_output=True, text=True)
        assert result.returncode == 0, (option, result.stdout, result.stderr)
        calls = log.read_text(encoding="utf-8")
        for fragment in fragments:
            assert fragment in calls, (option, fragment, calls)


def test_docker_configuration_overrides_have_effective_container_wiring() -> None:
    compose_text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    mcp_runner = (ROOT / "scripts" / "run_mcp.sh").read_text(encoding="utf-8")

    for key in ("AGENT_SPEAK_DATA_PATH", "AGENT_SPEAK_RUNTIME_PATH", "AGENT_SPEAK_MODELS_PATH"):
        assert key in compose_text and key in env
    assert "AGENT_SPEAK_DATA_DIR=data" not in env
    assert "AGENT_SPEAK_RUNTIME_DIR=runtime" not in env
    assert '-e AGENT_SPEAK_URL=' in mcp_runner


def test_run_script_prepares_custom_persistent_paths_and_reports_effective_host(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    paths = {name: tmp_path / name for name in ("private-data", "private-runtime", "private-models")}
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$*\" == 'compose config --environment' ]]; then\n"
        f"  echo 'AGENT_SPEAK_DATA_PATH={paths['private-data']}'\n"
        f"  echo 'AGENT_SPEAK_RUNTIME_PATH={paths['private-runtime']}'\n"
        f"  echo 'AGENT_SPEAK_MODELS_PATH={paths['private-models']}'\n"
        "  echo 'AGENT_SPEAK_PUBLISH_HOST=192.0.2.10'\n"
        "  echo 'AGENT_SPEAK_PORT=9876'\n"
        "  echo 'AGENT_SPEAK_UID=1234'\n"
        "  echo 'AGENT_SPEAK_GID=1235'\n"
        "  echo 'AGENT_SPEAK_AUDIO_GID=1236'\n"
        "fi\n"
        "if [[ \"$1 $2\" == 'compose ps' ]]; then echo 'fake-container'; fi\n"
        "if [[ \"$1\" == 'inspect' ]]; then echo 'healthy'; fi\n"
        "if [[ \"$*\" == *'arecord -l'* || \"$*\" == *'aplay -l'* ]]; then echo 'no soundcards found...'; fi\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}"}
    for key in (
        "AGENT_SPEAK_DATA_PATH", "AGENT_SPEAK_RUNTIME_PATH", "AGENT_SPEAK_MODELS_PATH",
        "AGENT_SPEAK_PUBLISH_HOST", "AGENT_SPEAK_PORT", "AGENT_SPEAK_UID", "AGENT_SPEAK_GID",
        "AGENT_SPEAK_AUDIO_GID",
    ):
        env.pop(key, None)

    result = subprocess.run([str(ROOT / "run.sh"), "--status"], cwd=ROOT, env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert all(path.is_dir() for path in paths.values())
    assert "web=http://192.0.2.10:9876" in result.stdout
    assert "capture=unavailable playback=unavailable" in result.stdout


def test_mcp_runner_only_uses_direct_python_inside_the_gateway_image() -> None:
    source = (ROOT / "scripts" / "run_mcp.sh").read_text(encoding="utf-8")
    assert '[[ -f /.dockerenv && -d /app/src/agent_speak ]]' in source


def test_github_readmes_are_bilingual_and_english_is_default() -> None:
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    traditional_chinese = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")

    assert "English | [繁體中文](README.zh-TW.md)" in english
    assert "[English](README.md) | 繁體中文" in traditional_chinese
    assert "./run.sh --build" in english and "./run.sh --build" in traditional_chinese
    assert "Docker" in english and "Docker" in traditional_chinese
    assert "./scripts/setup.sh" not in english
    assert "從 clone 到啟動" not in traditional_chinese
    assert english.count("繁體中文") <= 2


def test_skill_and_specs_document_docker_mcp_and_hardware_contract() -> None:
    skill = (ROOT / "skills" / "agent-speak" / "SKILL.md").read_text(encoding="utf-8")
    runtime = (ROOT / "spec" / "RUNTIME.md").read_text(encoding="utf-8")
    mcp = (ROOT / "spec" / "SKILL_AND_MCP.md").read_text(encoding="utf-8")
    project_map = (ROOT / "spec" / "PROJECT_MAP.md").read_text(encoding="utf-8")

    for text in (skill, runtime, mcp):
        assert "./run.sh --build" in text
        assert "/dev/snd" in text
    assert "Docker" in project_map
    assert "scripts/run_mcp.sh" in mcp


def _copy_smoke_script(tmp_path: Path, name: str) -> Path:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    target = scripts_dir / name
    target.write_text((ROOT / "scripts" / name).read_text(encoding="utf-8"), encoding="utf-8")
    target.chmod(0o755)
    return target


def test_smoke_scripts_prefer_a_running_docker_gateway(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "docker.log"
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n"
        "if [[ \"$*\" == 'compose ps --status running -q gateway' ]]; then echo gateway-id; exit 0; fi\n"
        "if [[ \"$1 $2\" == 'compose exec' ]]; then input=$(cat); [[ \"$input\" == *urllib.request* ]] || exit 9; exit 0; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_DOCKER_LOG": str(log),
        "API_BASE": "http://127.0.0.1:9876",
    }

    for name, success_marker in (
        ("health_smoke.sh", "HEALTH_SMOKE_OK"),
        ("smoke_api.sh", "API_SMOKE_OK"),
    ):
        script = _copy_smoke_script(tmp_path, name)
        result = subprocess.run([str(script)], cwd=tmp_path, env=env, capture_output=True, text=True)
        assert result.returncode == 0, (name, result.stdout, result.stderr)
        assert success_marker in result.stdout

    calls = log.read_text(encoding="utf-8")
    assert calls.count("compose ps --status running -q gateway") == 2
    assert calls.count("compose exec -T") >= 2
    assert calls.count("API_BASE=http://127.0.0.1:8765") >= 2
    assert "API_BASE=http://127.0.0.1:9876" not in calls


def test_smoke_scripts_fall_back_to_project_venv_without_a_running_gateway(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    docker.chmod(0o755)
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/usr/bin/env bash\ncat >/dev/null\n", encoding="utf-8")
    venv_python.chmod(0o755)
    env = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    for name, success_marker in (
        ("health_smoke.sh", "HEALTH_SMOKE_OK"),
        ("smoke_api.sh", "API_SMOKE_OK"),
    ):
        script = _copy_smoke_script(tmp_path, name)
        result = subprocess.run([str(script)], cwd=tmp_path, env=env, capture_output=True, text=True)
        assert result.returncode == 0, (name, result.stdout, result.stderr)
        assert success_marker in result.stdout


def test_runtime_spec_documents_docker_aware_smoke_scripts() -> None:
    runtime = (ROOT / "spec" / "RUNTIME.md").read_text(encoding="utf-8")
    testing = (ROOT / "spec" / "TESTING.md").read_text(encoding="utf-8")
    for name in ("health_smoke.sh", "smoke_api.sh"):
        assert name in runtime
        assert name in testing
    assert "Docker" in runtime and "fallback" in runtime
