import struct

import pytest

from agent_speak.realtime import RealtimeCoordinator
from agent_speak.realtime_queue import TextJob


class FakeVAD:
    def score(self, frame: bytes) -> float:
        return 0.9 if any(frame) else 0.0

    def reset(self) -> None:
        pass


class FakeASR:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def transcribe_mode(self, audio: bytes, mode: str, speech_language: str) -> str:
        self.calls.append((mode, speech_language))
        return "因為" if mode == "partial" else "因為需要測試"


class FakeText:
    def __init__(self) -> None:
        self.detect_languages: list[str] = []
        self.revise_languages: list[str] = []

    def detect(self, text: str, speech_language: str) -> tuple[bool, str]:
        self.detect_languages.append(speech_language)
        return (not text.endswith("因為"), "semantic")

    def revise(self, previous: str, current: str, speech_language: str):
        from agent_speak.realtime_models import CorrectionRevision

        self.revise_languages.append(speech_language)
        return CorrectionRevision(previous, current + "。", True)


@pytest.mark.anyio
async def test_coordinator_streams_partial_final_revision_and_returns_to_listening() -> None:
    asr = FakeASR()
    text = FakeText()
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=asr, text=text)
    stream = await coordinator.open("session", "ja")
    await stream.start()
    voice = struct.pack("<320h", *([10_000] * 320))
    silence = bytes(640)
    for _ in range(50):
        await stream.accept_pcm(voice)
    for _ in range(45):
        await stream.accept_pcm(silence)
    # Browser audio arrives in real time, so the semantic endpoint worker gets
    # a chance to extend the 900 ms candidate before the 1.8 s hard endpoint.
    await stream.wait_idle()
    assert "endpoint.extended" in [event.type for event in stream.history]
    for _ in range(45):
        await stream.accept_pcm(silence)
    await stream.wait_idle()
    types = [event.type for event in stream.history]
    assert "asr.partial" in types
    assert "asr.final" in types
    assert "transcript.revised" in types
    assert "utterance.completed" in types
    assert stream.state == "listening"
    assert {language for _, language in asr.calls} == {"ja"}
    assert text.detect_languages == ["ja"]
    assert text.revise_languages == ["ja"]
    await coordinator.close()


@pytest.mark.anyio
async def test_stop_finalizes_active_audio_without_agent_or_tts() -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    stream = await coordinator.open("session", "zh-TW")
    await stream.start()
    voice = struct.pack("<320h", *([10_000] * 320))
    for _ in range(20):
        await stream.accept_pcm(voice)
    await stream.stop()
    assert stream.state == "stopped"
    assert stream.history[-1].type == "stream.stopped"
    assert not any(event.type.startswith(("agent.", "tts.")) for event in stream.history)
    await coordinator.close()


@pytest.mark.anyio
async def test_invalid_pcm_frame_is_rejected_before_vad() -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    stream = await coordinator.open("session", "ko")
    await stream.start()
    with pytest.raises(Exception, match="PCM frame"):
        await stream.accept_pcm(b"short")
    await coordinator.close()


@pytest.mark.anyio
async def test_existing_realtime_stream_keeps_its_frozen_language() -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    stream = await coordinator.open("session", "en")

    assert await coordinator.open("session", "en") is stream
    with pytest.raises(RuntimeError, match="language mismatch"):
        await coordinator.open("session", "ko")

    assert stream.speech_language == "en"
    await coordinator.close()


@pytest.mark.anyio
async def test_failed_endpoint_provider_extends_language_specific_continuation() -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    stream = await coordinator.open("session", "en")

    class CandidateDetector:
        extended = False
        finalized = False

        def finalize_candidate(self):
            self.finalized = True
            return None

        def extend_endpoint(self) -> bool:
            self.extended = True
            return True

        def reset(self) -> None:
            pass

    detector = CandidateDetector()
    stream.detector = detector  # type: ignore[assignment]
    job = TextJob("session", "utterance", "endpoint", "", "I stopped because", "en")

    await stream._accept_text_result(job, None, RuntimeError("worker failed"))

    assert detector.extended is True
    assert detector.finalized is False
    await coordinator.close()
