from __future__ import annotations

import httpx
import pytest

from agent_speak.audio import decode_wav
from agent_speak.errors import PlatformError
from agent_speak.tts_clone import VoxCPMClient, assess_reference, compile_style_cues
from tests.audio_fixtures import wav_bytes


def test_style_cues_compile_to_allowlisted_natural_language() -> None:
    assert compile_style_cues(["warm", "light_laugh"], "Hello") == (
        "(warm delivery, speaking with a light laugh)Hello"
    )

    with pytest.raises(PlatformError) as error:
        compile_style_cues(["[unknown]"], "Hello")

    assert error.value.code == "invalid_style_cue"


def test_reference_assessment_reports_good_voice() -> None:
    wav = wav_bytes(seconds=10.0, amplitude=0.25)

    result = assess_reference(
        wav,
        max_bytes=8 * 1024 * 1024,
        rms_threshold=0.015,
    )

    assert result.quality == "good"
    assert result.duration_seconds == pytest.approx(10.0)
    assert result.voiced_ratio >= 0.9


@pytest.mark.parametrize(
    ("duration", "amplitude", "quality"),
    [(3.0, 0.2, "too_short"), (10.0, 0.001, "too_quiet"), (31.0, 0.2, "too_long")],
)
def test_reference_assessment_returns_bounded_quality(
    duration: float, amplitude: float, quality: str
) -> None:
    assert assess_reference(
        wav_bytes(seconds=duration, amplitude=amplitude),
        max_bytes=8 * 1024 * 1024,
        rms_threshold=0.015,
    ).quality == quality


def test_voxcpm_client_sends_official_speech_shape() -> None:
    captured: dict[str, object] = {}

    def request(payload: dict[str, object]) -> bytes:
        captured.update(payload)
        return wav_bytes(rate=48_000, seconds=1.0)

    client = VoxCPMClient("http://tts-worker:8000", request=request)
    result = client.synthesize(
        text="(warm delivery)Hello",
        reference_wav=wav_bytes(rate=16_000, seconds=10.0),
    )

    assert captured["model"] == "voxcpm2"
    assert captured["input"] == "(warm delivery)Hello"
    assert captured["voice"] == "default"
    assert captured["response_format"] == "wav"
    assert str(captured["ref_audio"]).startswith("data:audio/wav;base64,")
    assert (
        decode_wav(
            result,
            max_bytes=32 * 1024 * 1024,
            max_seconds=120,
            stage="tts_clone",
        ).sample_rate
        == 48_000
    )


def test_voxcpm_client_maps_oom_without_leaking_worker_message() -> None:
    def fail(_: dict[str, object]) -> bytes:
        raise httpx.HTTPStatusError(
            "CUDA out of memory: private worker detail",
            request=httpx.Request("POST", "http://tts-worker:8000/v1/audio/speech"),
            response=httpx.Response(500),
        )

    client = VoxCPMClient("http://tts-worker:8000", request=fail)

    with pytest.raises(PlatformError) as error:
        client.synthesize(text="hello", reference_wav=None)

    assert error.value.code == "gpu_out_of_memory"
    assert "private worker detail" not in error.value.message


def test_voxcpm_client_rejects_non_48khz_output() -> None:
    client = VoxCPMClient(
        "http://tts-worker:8000",
        request=lambda _: wav_bytes(rate=16_000, seconds=1.0),
    )

    with pytest.raises(PlatformError) as error:
        client.synthesize(text="hello", reference_wav=None)

    assert error.value.code == "invalid_tts_audio"
