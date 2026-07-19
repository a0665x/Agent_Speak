from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "setup.sh": "SETUP_OK",
    "run.sh": "RUN_STARTING",
    "status.sh": "STATUS_OK",
    "test.sh": "TESTS_OK",
    "health_smoke.sh": "HEALTH_SMOKE_OK",
    "mic_smoke.sh": "MIC_SMOKE_OK",
    "smoke_api.sh": "API_SMOKE_OK",
}


def test_operator_scripts_are_executable_syntax_checked_and_signal_success() -> None:
    for name, signal in SCRIPTS.items():
        path = ROOT / "scripts" / name
        assert path.is_file(), name
        assert os.access(path, os.X_OK), name
        source = path.read_text()
        assert signal in source, name
        assert ".venv" in source, name
        assert "sudo pip" not in source and "pip install --user" not in source, name
        subprocess.run(["bash", "-n", str(path)], check=True)


def test_environment_example_and_readme_cover_docker_execution() -> None:
    env = (ROOT / ".env.example").read_text()
    readme = (ROOT / "README.md").read_text()

    for key in ("AGENT_SPEAK_PUBLISH_HOST", "AGENT_SPEAK_PORT", "AGENT_SPEAK_MAX_AUDIO_BYTES", "AGENT_SPEAK_MAX_AUDIO_SECONDS"):
        assert key in env
    for command in ("./run.sh --build", "./run.sh --status", "./run.sh --test", "./run.sh --down"):
        assert command in readme
    assert "not authentication" in readme.lower()
    assert "AGENT_SPEAK_PUBLISH_HOST=127.0.0.1" in env
    assert "/dev/snd" in readme and "Docker" in readme
    assert "private HTTPS" in readme


def test_runtime_companion_scripts_load_the_same_dotenv_as_run() -> None:
    for name in ("status.sh", "health_smoke.sh", "mic_smoke.sh", "smoke_api.sh"):
        source = (ROOT / "scripts" / name).read_text()
        assert 'source "$ROOT_DIR/.env"' in source, name


def test_setup_and_smoke_follow_package_and_artifact_truth() -> None:
    setup = (ROOT / "scripts/setup.sh").read_text()
    smoke = (ROOT / "scripts/smoke_api.sh").read_text()
    test_script = (ROOT / "scripts/test.sh").read_text()

    assert ".[test]" in setup and "packages=(" not in setup
    assert "RIFF" in smoke and "WAVE" in smoke and "audio/wav" in smoke
    assert "STATIC_CHECKS_SKIPPED" in test_script
    assert "pytest_and_static_checks_passed" not in test_script


def test_private_audio_feature_and_weight_extensions_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text().splitlines()

    for pattern in ("*.flac", "*.mp3", "*.m4a", "*.npy", "*.npz", "*.safetensors", "*.ckpt", "*.gguf"):
        assert pattern in ignore


def test_status_reports_stopped_with_nonzero_exit() -> None:
    environment = os.environ.copy()
    environment["AGENT_SPEAK_PORT"] = "65534"
    result = subprocess.run(
        [str(ROOT / "scripts" / "status.sh")],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "STATUS_STOPPED" in result.stdout


def test_api_spec_defines_endpoint_completion_as_informational() -> None:
    api = (ROOT / "spec" / "API.md").read_text().lower()

    assert "endpoint" in api
    assert "informational" in api
    assert "continues" in api
