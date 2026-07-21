"""Public speech-language values shared across session and worker boundaries."""

from __future__ import annotations

from typing import Literal


SpeechLanguage = Literal["auto", "en", "zh-TW", "ja", "ko"]
DEFAULT_SPEECH_LANGUAGE: SpeechLanguage = "zh-TW"


def whisper_language(value: SpeechLanguage) -> str | None:
    return {
        "auto": None,
        "en": "en",
        "zh-TW": "zh",
        "ja": "ja",
        "ko": "ko",
    }[value]
