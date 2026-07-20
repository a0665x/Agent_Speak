from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_speak.accelerators import ASRDeviceSelection, select_asr_device
from agent_speak.config import Settings
from agent_speak.errors import PlatformError


def test_cpu_mode_skips_cuda_probe() -> None:
    called = False

    def probe() -> bool:
        nonlocal called
        called = True
        return True

    selected = select_asr_device("cpu", "int8", "float16", probe)

    assert selected == ASRDeviceSelection("cpu", "int8", None)
    assert called is False


def test_auto_uses_cuda_when_probe_succeeds() -> None:
    selected = select_asr_device("auto", "int8", "float16", lambda: True)

    assert selected == ASRDeviceSelection("cuda", "float16", None)


def test_auto_falls_back_once_when_probe_fails() -> None:
    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        raise RuntimeError("libcudnn unavailable")

    selected = select_asr_device("auto", "int8", "float16", probe)

    assert selected.device == "cpu"
    assert selected.compute_type == "int8"
    assert selected.fallback_reason == "CUDA probe failed"
    assert calls == 1


def test_nvidia_mode_rejects_failed_cuda_probe() -> None:
    with pytest.raises(PlatformError, match="NVIDIA acceleration was required") as captured:
        select_asr_device("nvidia", "int8", "float16", lambda: False)

    assert captured.value.code == "provider_unavailable"
    assert captured.value.stage == "asr"


def test_settings_validate_accelerator_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_SPEAK_ACCELERATOR", "nvidia")
    monkeypatch.setenv("AGENT_SPEAK_ASR_CUDA_COMPUTE_TYPE", "float16")
    settings = Settings.from_env()

    assert settings.accelerator == "nvidia"
    assert settings.asr_cuda_compute_type == "float16"

    monkeypatch.setenv("AGENT_SPEAK_ACCELERATOR", "rocm")
    with pytest.raises(ValidationError):
        Settings.from_env()
