from __future__ import annotations

import io
import json
import subprocess
import wave
from pathlib import Path

import pytest

from agent_speak.mcp_server import AgentSpeakControl, ControlError, GatewayHTTPClient


def valid_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\x01\x00" * 1600)
    return output.getvalue()


class FakeHTTP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    def json(self, method: str, path: str, body: object | None = None) -> dict:
        self.calls.append((method, path, body))
        responses = {
            ("GET", "/api/v1/health"): {"status": "ok", "version": "0.1.0"},
            ("GET", "/api/v1/capabilities"): {"providers": {"asr": {"name": "fake"}}},
            ("POST", "/api/v1/audio/asr"): {"text": "測試語音"},
            ("POST", "/api/v1/tts/synthesize"): {"audio_url": "/api/v1/artifacts/test.wav"},
        }
        return responses[(method, path)]

    def wav(self, method: str, path: str, payload: bytes) -> dict:
        self.calls.append((method, path, payload))
        return self.json(method, path)

    def bytes(self, path: str) -> bytes:
        self.calls.append(("GET_BYTES", path, None))
        return valid_wav()


def completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_gateway_client_allows_loopback_http_and_remote_https() -> None:
    assert GatewayHTTPClient("http://127.0.0.1:8765").base_url == "http://127.0.0.1:8765"
    assert GatewayHTTPClient("https://voice.example.com").base_url == "https://voice.example.com"


@pytest.mark.parametrize(
    "url",
    [
        "http://voice.example.com",
        "http://user:password@127.0.0.1:8765",
        "http://127.0.0.1:8765/base",
        "https://voice.example.com?token=secret",
        "https://voice.example.com/#fragment",
    ],
)
def test_gateway_client_rejects_unsafe_origins(url: str) -> None:
    with pytest.raises(ValueError):
        GatewayHTTPClient(url)


def test_status_combines_gateway_health_and_capabilities() -> None:
    control = AgentSpeakControl(http=FakeHTTP(), runner=lambda *args, **kwargs: completed())
    result = control.status()
    assert result["reachable"] is True
    assert result["health"]["status"] == "ok"
    assert result["capabilities"]["providers"]["asr"]["name"] == "fake"


def test_audio_devices_are_listed_without_shell_and_with_timeout() -> None:
    calls: list[tuple[list[str], float]] = []

    def runner(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append((command, timeout))
        return completed("card 1: USB [USB Audio], device 0: Audio [USB Audio]")

    result = AgentSpeakControl(http=FakeHTTP(), runner=runner).list_audio_devices()
    assert result["capture"]["available"] is True
    assert result["playback"]["available"] is True
    assert calls == [(["arecord", "-l"], 5.0), (["aplay", "-l"], 5.0)]


def test_list_audio_devices_reports_missing_commands() -> None:
    def runner(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(command[0])

    result = AgentSpeakControl(http=FakeHTTP(), runner=runner).list_audio_devices()
    assert result["capture"]["available"] is False
    assert "not installed" in result["capture"]["error"]


def test_listen_once_records_bounded_wav_then_uses_http_asr(tmp_path: Path) -> None:
    http = FakeHTTP()

    def runner(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        Path(command[-1]).write_bytes(valid_wav())
        assert command[:2] == ["arecord", "-q"]
        assert timeout == 5.0
        return completed()

    result = AgentSpeakControl(http=http, runner=runner, temp_dir=tmp_path).listen_once(
        duration_seconds=2, device="plughw:1,0", user_confirmed=True
    )
    assert result["text"] == "測試語音"
    assert any(call[0:2] == ("POST", "/api/v1/audio/asr") for call in http.calls)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("device", ["; rm -rf /", "hw:1,0 --use-strftime", "../../dev/null"])
def test_listen_once_rejects_unsafe_device(device: str) -> None:
    with pytest.raises(ControlError, match="Invalid ALSA device"):
        AgentSpeakControl(http=FakeHTTP(), runner=lambda *args, **kwargs: completed()).listen_once(
            device=device, user_confirmed=True
        )


def test_microphone_tools_require_explicit_user_confirmation() -> None:
    control = AgentSpeakControl(http=FakeHTTP(), runner=lambda *args, **kwargs: completed())

    with pytest.raises(ControlError, match="explicit user confirmation"):
        control.microphone_smoke()
    with pytest.raises(ControlError, match="explicit user confirmation"):
        control.listen_once()


def test_microphone_smoke_rejects_invalid_wav(tmp_path: Path) -> None:
    def runner(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        Path(command[-1]).write_bytes(b"RIFF-not-a-valid-wave")
        return completed()

    control = AgentSpeakControl(http=FakeHTTP(), runner=runner, temp_dir=tmp_path)
    with pytest.raises(ControlError, match="valid PCM WAV"):
        control.microphone_smoke(user_confirmed=True)


def test_speak_does_not_claim_playback_without_speaker(tmp_path: Path) -> None:
    def runner(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        if command == ["aplay", "-l"]:
            return completed("no soundcards found...", returncode=1)
        return completed()

    result = AgentSpeakControl(http=FakeHTTP(), runner=runner, temp_dir=tmp_path).speak(
        "你好", playback=True, user_confirmed=True
    )
    assert result["synthesized"] is True
    assert result["played"] is False
    assert "No playback device" in result["playback_error"]


def test_speak_downloads_and_plays_generated_wav(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def runner(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command == ["aplay", "-l"]:
            return completed("card 0: Audio [Audio], device 0: Playback [Playback]")
        return completed()

    result = AgentSpeakControl(http=FakeHTTP(), runner=runner, temp_dir=tmp_path).speak(
        "你好", playback=True, user_confirmed=True
    )
    assert result["played"] is True
    assert commands[-1][0:2] == ["aplay", "-q"]
    assert list(tmp_path.iterdir()) == []


def test_speak_requires_confirmation_before_physical_playback() -> None:
    control = AgentSpeakControl(http=FakeHTTP(), runner=lambda *args, **kwargs: completed())

    with pytest.raises(ControlError, match="explicit user confirmation"):
        control.speak("你好", playback=True)
