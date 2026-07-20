import pytest

from agent_speak.realtime_endpoint import DetectorConfig, UtteranceDetector


FRAME = 640


def config(**overrides: int) -> DetectorConfig:
    values = {
        "frame_ms": 20,
        "pre_roll_ms": 300,
        "min_speech_ms": 250,
        "endpoint_ms": 900,
        "hard_endpoint_ms": 1_800,
        "max_utterance_ms": 30_000,
    }
    values.update(overrides)
    return DetectorConfig(**values)


def test_detector_emits_candidate_at_900ms_and_hard_final_at_1800ms() -> None:
    detector = UtteranceDetector(config())
    actions = []
    for _ in range(15):
        actions.extend(detector.accept(b"v" * FRAME, voiced=True))
    for _ in range(45):
        actions.extend(detector.accept(b"s" * FRAME, voiced=False))
    assert [item.kind for item in actions] == ["speech_started", "endpoint_candidate"]

    detector.extend_endpoint()
    actions = []
    for _ in range(45):
        actions.extend(detector.accept(b"s" * FRAME, voiced=False))
    assert actions[-1].kind == "utterance_final"
    assert actions[-1].silence_ms == 1_800


def test_resumed_speech_cancels_candidate_and_keeps_same_utterance() -> None:
    detector = UtteranceDetector(DetectorConfig.defaults())
    started = []
    for _ in range(15):
        started.extend(detector.accept(b"v" * FRAME, voiced=True))
    utterance_id = started[0].utterance_id
    for _ in range(45):
        detector.accept(b"s" * FRAME, voiced=False)

    actions = detector.accept(b"v" * FRAME, voiced=True)
    assert [item.kind for item in actions] == ["endpoint_cancelled"]
    assert actions[0].utterance_id == utterance_id


def test_short_noise_is_rejected_and_pre_roll_stays_bounded() -> None:
    detector = UtteranceDetector(config())
    for _ in range(5):
        assert detector.accept(b"n" * FRAME, voiced=True) == []
    for _ in range(30):
        assert detector.accept(b"s" * FRAME, voiced=False) == []

    actions = []
    for _ in range(13):
        actions.extend(detector.accept(b"v" * FRAME, voiced=True))
    assert [item.kind for item in actions] == ["speech_started"]
    assert len(actions[0].pcm) == 15 * FRAME


def test_candidate_can_be_finalized_immediately() -> None:
    detector = UtteranceDetector(config())
    for _ in range(15):
        detector.accept(b"v" * FRAME, voiced=True)
    for _ in range(45):
        detector.accept(b"s" * FRAME, voiced=False)

    action = detector.finalize_candidate()
    assert action is not None
    assert action.kind == "utterance_final"
    assert action.pcm
    assert detector.finalize_candidate() is None


def test_max_duration_forces_final_and_reset_discards_all_state() -> None:
    detector = UtteranceDetector(
        config(pre_roll_ms=40, min_speech_ms=40, max_utterance_ms=100)
    )
    actions = []
    for _ in range(5):
        actions.extend(detector.accept(b"v" * FRAME, voiced=True))
    assert [item.kind for item in actions] == ["speech_started", "utterance_final"]

    detector.reset()
    assert detector.accept(b"s" * FRAME, voiced=False) == []
    assert detector.finalize_candidate() is None


def test_invalid_timing_order_is_rejected() -> None:
    with pytest.raises(ValueError, match="endpoint"):
        config(endpoint_ms=1_800, hard_endpoint_ms=1_800)
