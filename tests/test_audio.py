from __future__ import annotations

import pytest

from agent_speak.audio import EnergyVAD, decode_wav
from agent_speak.errors import PlatformError

from .audio_fixtures import wav_bytes


def test_decode_wav_returns_bounded_normalized_pcm() -> None:
    decoded = decode_wav(wav_bytes(frequency=440, amplitude=0.4), max_bytes=100_000, max_seconds=1)

    assert decoded.sample_rate == 16_000
    assert decoded.channels == 1
    assert decoded.duration_seconds == pytest.approx(0.25, abs=0.001)
    assert decoded.peak == pytest.approx(0.4, abs=0.01)
    assert decoded.rms > 0.25
    assert decoded.samples.dtype.name == "float32"


@pytest.mark.parametrize(
    ("payload", "max_bytes", "max_seconds", "code"),
    [
        (b"not-wave", 100_000, 1, "invalid_wav"),
        (wav_bytes(seconds=0.25), 100, 1, "audio_too_large"),
        (wav_bytes(seconds=1), 100_000, 0.1, "audio_too_long"),
    ],
)
def test_decode_wav_rejects_malformed_and_out_of_bounds(
    payload: bytes, max_bytes: int, max_seconds: float, code: str
) -> None:
    with pytest.raises(PlatformError) as caught:
        decode_wav(payload, max_bytes=max_bytes, max_seconds=max_seconds)

    assert caught.value.code == code
    assert caught.value.stage == "vad"


def test_energy_vad_distinguishes_silence_and_tone() -> None:
    vad = EnergyVAD(max_bytes=100_000, max_seconds=1, rms_threshold=0.02)

    silence = vad.detect(wav_bytes(amplitude=0))
    tone = vad.detect(wav_bytes(amplitude=0.25))

    assert silence["voiced"] is False
    assert tone["voiced"] is True
    assert tone["rms"] > silence["rms"]
