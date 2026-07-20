import struct

import pytest

from agent_speak.realtime import RealtimeCoordinator


class FakeVAD:
    def score(self, frame: bytes) -> float:
        return 0.9 if any(frame) else 0.0

    def reset(self) -> None:
        pass


class FakeASR:
    def transcribe_mode(self, audio: bytes, mode: str) -> str:
        return "因為" if mode == "partial" else "因為需要測試"


class FakeText:
    def detect(self, text: str) -> tuple[bool, str]:
        return (not text.endswith("因為"), "semantic")

    def revise(self, previous: str, current: str):
        from agent_speak.realtime_models import CorrectionRevision

        return CorrectionRevision(previous, current + "。", True)


@pytest.mark.anyio
async def test_coordinator_streams_partial_final_revision_and_returns_to_listening() -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    stream = await coordinator.open("session")
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
    await coordinator.close()


@pytest.mark.anyio
async def test_stop_finalizes_active_audio_without_agent_or_tts() -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    stream = await coordinator.open("session")
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
    stream = await coordinator.open("session")
    await stream.start()
    with pytest.raises(Exception, match="PCM frame"):
        await stream.accept_pcm(b"short")
    await coordinator.close()
