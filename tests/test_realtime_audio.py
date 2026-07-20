import struct

import numpy as np
import pytest

from agent_speak.errors import PlatformError
from agent_speak.realtime_audio import EnergyFrameVAD, PCMContract, SileroFrameVAD, pcm16_to_wav


def frame(amplitude: int, samples: int = 320) -> bytes:
    return struct.pack(f"<{samples}h", *([amplitude] * samples))


def test_pcm_contract_accepts_exact_20ms_frame_and_rejects_wrong_size() -> None:
    contract = PCMContract(sample_rate=16_000, channels=1, frame_ms=20)
    assert contract.validate(frame(1)) == frame(1)
    with pytest.raises(PlatformError, match="PCM frame"):
        contract.validate(frame(1, 319))


def test_pcm16_to_wav_produces_valid_mono_header() -> None:
    payload = pcm16_to_wav(frame(2_000), sample_rate=16_000)
    assert payload[:4] == b"RIFF"
    assert payload[8:12] == b"WAVE"


def test_energy_fallback_separates_silence_and_voice() -> None:
    vad = EnergyFrameVAD(threshold=0.02)
    assert vad.score(frame(0)) == 0.0
    assert vad.score(frame(12_000)) > 0.5


class FakeSileroModel:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []
        self.reset_count = 0

    def __call__(self, samples, sample_rate: int):
        self.calls.append((len(samples), sample_rate))
        return 0.75

    def reset_states(self) -> None:
        self.reset_count += 1


def test_silero_adapter_buffers_512_samples_and_resets_each_stream() -> None:
    model = FakeSileroModel()
    vad = SileroFrameVAD(model=model)

    assert vad.score(frame(1)) == 0.0
    assert vad.score(frame(1)) == 0.75
    assert model.calls == [(512, 16_000)]

    vad.reset()
    assert model.reset_count == 1
    assert vad.score(frame(1)) == 0.0


class FakeOnnxSession:
    def __init__(self) -> None:
        self.states: list[np.ndarray] = []

    def run(self, _outputs, inputs):
        self.states.append(inputs["state"].copy())
        return np.array([[0.6]], dtype=np.float32), np.ones((2, 1, 128), dtype=np.float32)


def test_silero_onnx_session_state_is_reset_without_torch() -> None:
    session = FakeOnnxSession()
    vad = SileroFrameVAD(session=session)

    vad.score(frame(1))
    assert vad.score(frame(1)) == pytest.approx(0.6)
    vad.score(frame(1))
    assert vad.score(frame(1)) == pytest.approx(0.6)
    assert np.count_nonzero(session.states[0]) == 0
    assert np.count_nonzero(session.states[1]) > 0

    vad.reset()
    vad.score(frame(1))
    vad.score(frame(1))
    assert np.count_nonzero(session.states[2]) == 0
