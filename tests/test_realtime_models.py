import pytest
from pydantic import ValidationError

from agent_speak.config import Settings
from agent_speak.realtime_models import RealtimeEvent, StreamStart


def test_stream_start_accepts_only_approved_pcm_contract() -> None:
    start = StreamStart(
        type="stream.start",
        format="pcm_s16le",
        sample_rate=16_000,
        channels=1,
        frame_ms=20,
    )
    assert start.model_dump() == {
        "type": "stream.start",
        "format": "pcm_s16le",
        "sample_rate": 16_000,
        "channels": 1,
        "frame_ms": 20,
    }
    with pytest.raises(ValidationError):
        StreamStart(
            type="stream.start",
            format="float32",
            sample_rate=48_000,
            channels=2,
            frame_ms=100,
        )


def test_realtime_event_requires_session_sequence_and_typed_payload() -> None:
    event = RealtimeEvent(
        sequence=1,
        session_id="session",
        utterance_id="utt",
        type="asr.partial",
        data={"text": "你好"},
    )
    assert event.sequence == 1
    assert event.data["text"] == "你好"


def test_realtime_defaults_match_approved_design() -> None:
    settings = Settings()
    assert settings.realtime_frame_ms == 20
    assert settings.realtime_pre_roll_ms == 300
    assert settings.realtime_min_speech_ms == 250
    assert settings.realtime_partial_interval_ms == 800
    assert settings.realtime_endpoint_ms == 900
    assert settings.realtime_hard_endpoint_ms == 1_800
    assert settings.realtime_endpoint_timeout_ms == 250
    assert "realtime_expected_device" not in Settings.model_fields
    assert settings.asr_worker_url == ""
    assert settings.correction_worker_url == ""
    assert settings.effective_accelerator == "cpu"
