import struct
import json

import pytest

from agent_speak.realtime import RealtimeCoordinator
from agent_speak.config import Settings
from agent_speak.diagnostic_logging import configure_diagnostic_logging
from agent_speak.realtime_queue import ASRJob, TextJob


class FakeVAD:
    def score(self, frame: bytes) -> float:
        return 0.9 if any(frame) else 0.0

    def reset(self) -> None:
        pass


class FakeASR:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str]] = []

    def transcribe_mode(
        self,
        audio: bytes,
        mode: str,
        speech_language: str,
        asr_model: str = "qwen3-asr-1.7b",
        session_id: str = "session",
    ) -> str:
        self.calls.append((mode, speech_language, asr_model, session_id))
        return "因為" if mode == "partial" else "因為需要測試"


class FailingRealtimeASR(FakeASR):
    def transcribe_mode(
        self,
        audio: bytes,
        mode: str,
        speech_language: str,
        asr_model: str = "qwen3-asr-1.7b",
        session_id: str = "session",
    ) -> str:
        raise RuntimeError("private speech provider detail")


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
    assert {language for _, language, _, _ in asr.calls} == {"ja"}
    assert {model for _, _, model, _ in asr.calls} == {"qwen3-asr-1.7b"}
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
async def test_coordinator_logs_asr_failure_without_session_or_provider_message(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime")
    logger = configure_diagnostic_logging(
        service="realtime-test",
        runtime_dir=settings.runtime_dir,
        stream=False,
    )
    coordinator = RealtimeCoordinator(
        settings,
        vad=FakeVAD(),
        asr=FailingRealtimeASR(),
        text=FakeText(),
        logger=logger,
    )
    stream = await coordinator.open("private-session", "zh-TW", "qwen3-asr-1.7b")
    await stream.start()
    voice = struct.pack("<320h", *([10_000] * 320))
    for _ in range(50):
        await stream.accept_pcm(voice)
    await stream.wait_idle()
    await coordinator.close()

    records = [
        json.loads(line)
        for line in (settings.runtime_dir / "logs" / "realtime-test.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    failure = next(record for record in records if record["event"] == "realtime.asr.failed")
    rendered = json.dumps(failure)
    assert failure["model"] == "qwen3-asr-1.7b"
    assert failure["mode"] == "final"
    assert failure["exception_type"] == "RuntimeError"
    assert "private-session" not in rendered
    assert "private speech provider detail" not in rendered


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


class FakeModelControl:
    def __init__(self) -> None:
        self.acquired: list[tuple[str, str]] = []
        self.released: list[str] = []

    def acquire(self, session_id: str, asr_model: str) -> dict[str, object]:
        self.acquired.append((session_id, asr_model))
        return {}

    def release(self, session_id: str) -> dict[str, object]:
        self.released.append(session_id)
        return {}


@pytest.mark.anyio
async def test_realtime_uses_frozen_models_and_releases_lease() -> None:
    control = FakeModelControl()
    coordinator = RealtimeCoordinator(
        RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText()).settings,
        vad=FakeVAD(),
        asr=FakeASR(),
        text=FakeText(),
        model_control=control,
    )

    stream = await coordinator.open(
        "session-a",
        "zh-TW",
        "breeze-asr-25",
        "disabled",
    )
    await stream.stop()

    assert control.acquired == [("session-a", "breeze-asr-25")]
    assert control.released == ["session-a"]
    assert stream.asr_model == "breeze-asr-25"
    assert stream.correction_model == "disabled"
    await coordinator.close()


@pytest.mark.anyio
async def test_existing_stream_rejects_frozen_model_mismatch() -> None:
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=FakeText())
    await coordinator.open("session", "en", "qwen3-asr-1.7b", "qwen2.5-correction")

    with pytest.raises(RuntimeError, match="model mismatch"):
        await coordinator.open("session", "en", "breeze-asr-25", "qwen2.5-correction")
    with pytest.raises(RuntimeError, match="model mismatch"):
        await coordinator.open("session", "en", "qwen3-asr-1.7b", "disabled")

    await coordinator.close()


@pytest.mark.anyio
async def test_disabled_correction_completes_with_raw_final_asr() -> None:
    text = FakeText()
    coordinator = RealtimeCoordinator.for_test(vad=FakeVAD(), asr=FakeASR(), text=text)
    stream = await coordinator.open("session", "zh-TW", "breeze-asr-25", "disabled")
    job = ASRJob("session", "utterance", 1, "final", b"pcm", "zh-TW", "breeze-asr-25")

    await stream._accept_asr_result(job, "raw 中英 text", None)
    await stream.wait_idle()

    assert text.revise_languages == []
    assert stream.ledger.rows()[-1].text == "raw 中英 text"
    revision = next(event for event in stream.history if event.type == "transcript.revised")
    completed = next(event for event in stream.history if event.type == "utterance.completed")
    assert revision.data["policy"] == "disabled"
    assert completed.data["asr_model"] == "breeze-asr-25"
    assert completed.data["correction_model"] == "disabled"
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
