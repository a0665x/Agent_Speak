from pathlib import Path
import stat

import pytest
from pydantic import ValidationError

from agent_speak.config import Settings
from agent_speak.development import DevelopmentASR, DevelopmentAgent, DevelopmentCorrection, DevelopmentEndpoint, DevelopmentTTS
from agent_speak.providers import ASRProvider, AgentProvider, CorrectionProvider, EndpointProvider, TTSProvider
from agent_speak.schemas import ErrorEnvelope, PipelineEvent, ProviderCapability


def test_settings_load_typed_agent_speak_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENT_SPEAK_HOST", "127.0.0.1")
    monkeypatch.setenv("AGENT_SPEAK_PORT", "9876")
    monkeypatch.setenv("AGENT_SPEAK_MAX_AUDIO_BYTES", "4096")
    monkeypatch.setenv("AGENT_SPEAK_DATA_DIR", str(tmp_path / "private"))

    settings = Settings.from_env()

    assert settings.host == "127.0.0.1"
    assert settings.port == 9876
    assert settings.max_audio_bytes == 4096
    assert settings.data_dir == tmp_path / "private"


def test_settings_reject_invalid_port() -> None:
    with pytest.raises(ValidationError):
        Settings(port=70_000)


def test_settings_default_to_loopback_and_prepare_private_directories(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime")
    settings.prepare_directories()

    assert settings.host == "127.0.0.1"
    assert stat.S_IMODE(settings.data_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(settings.runtime_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((settings.runtime_dir / "artifacts").stat().st_mode) == 0o700


def test_public_contract_models_are_strictly_typed() -> None:
    capability = ProviderCapability(
        stage="asr",
        name="deterministic-asr",
        ready=True,
        development=True,
        limitations=["Not speech recognition."],
    )
    event = PipelineEvent(sequence=1, type="stage.started", stage="asr", data={})
    error = ErrorEnvelope.model_validate(
        {"error": {"code": "bad_audio", "message": "Invalid WAV", "stage": "vad", "retryable": False, "details": {}}}
    )

    assert capability.development is True
    assert event.sequence == 1
    assert error.error.code == "bad_audio"

    with pytest.raises(ValidationError):
        PipelineEvent(sequence=0, type="stage.started", data={})


def test_development_agent_uses_a_spoken_chinese_wrapper_for_chinese_input() -> None:
    assert DevelopmentAgent().respond("你好，測試。") == "開發模式回覆：我聽到「你好，測試。」"


def test_development_adapters_satisfy_typed_stage_protocols() -> None:
    assert isinstance(DevelopmentASR(), ASRProvider)
    assert isinstance(DevelopmentCorrection(), CorrectionProvider)
    assert isinstance(DevelopmentEndpoint(), EndpointProvider)
    assert isinstance(DevelopmentAgent(), AgentProvider)
    assert isinstance(DevelopmentTTS(), TTSProvider)
