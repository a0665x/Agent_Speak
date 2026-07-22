import pytest

from agent_speak.errors import PlatformError
from agent_speak.remote_asr import RemoteASRProvider


def test_remote_asr_keeps_existing_provider_signature() -> None:
    requests: list[dict[str, object]] = []
    provider = RemoteASRProvider(
        "http://asr-worker:8771",
        request=lambda payload: requests.append(payload) or {"text": "你好", "device": "cuda"},
    )
    assert provider.transcribe(b"RIFF-test-payload") == "你好"
    assert requests[0]["mode"] == "final"
    assert provider.device == "cuda"


def test_remote_asr_supports_partial_mode_and_rejects_invalid_response() -> None:
    provider = RemoteASRProvider(
        "http://asr-worker:8771",
        request=lambda _: {"text": "partial", "device": "cpu"},
    )
    assert provider.transcribe_mode(b"RIFF", "partial") == "partial"

    invalid = RemoteASRProvider(
        "http://asr-worker:8771",
        request=lambda _: {"text": 3, "device": "cpu"},
    )
    with pytest.raises(PlatformError, match="invalid"):
        invalid.transcribe(b"RIFF")


def test_remote_asr_forwards_explicit_session_language_without_changing_legacy_calls() -> None:
    requests: list[dict[str, object]] = []
    provider = RemoteASRProvider(
        "http://asr-worker:8771",
        request=lambda payload: requests.append(payload) or {"text": "hello", "device": "cuda"},
    )

    assert provider.transcribe_mode(b"RIFF", "partial", "en") == "hello"
    assert provider.transcribe_mode(b"RIFF", "final", "auto") == "hello"
    assert provider.transcribe_mode(b"RIFF", "final") == "hello"

    assert requests == [
        {"audio": b"RIFF", "mode": "partial", "speech_language": "en"},
        {"audio": b"RIFF", "mode": "final", "speech_language": "auto"},
        {"audio": b"RIFF", "mode": "final"},
    ]


def test_remote_asr_forwards_frozen_model_and_lease_owner() -> None:
    requests: list[dict[str, object]] = []
    provider = RemoteASRProvider(
        "http://asr-worker:8771",
        request=lambda payload: requests.append(payload)
        or {"text": "mixed speech", "device": "cuda"},
    )

    result = provider.transcribe_mode(
        b"RIFF",
        "final",
        "zh-TW",
        "breeze-asr-25",
        "session-a",
    )

    assert result == "mixed speech"
    assert requests == [
        {
            "audio": b"RIFF",
            "mode": "final",
            "speech_language": "zh-TW",
            "asr_model": "breeze-asr-25",
            "session_id": "session-a",
        }
    ]
