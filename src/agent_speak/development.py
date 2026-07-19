"""Deterministic offline providers for integration development, not model inference."""

from __future__ import annotations

import hashlib
import io
import math
import struct
import wave


class DevelopmentVAD:
    """Temporary byte-presence adapter; the real energy VAD is wired by audio.py."""

    def detect(self, audio: bytes) -> dict[str, object]:
        return {"voiced": bool(audio), "rms": 1.0 if audio else 0.0, "duration_seconds": 0.0}


class DevelopmentASR:
    def transcribe(self, audio: bytes) -> str:
        digest = hashlib.sha256(audio).hexdigest()[:8]
        return f"Development transcript [{digest}]"


class DevelopmentCorrection:
    def correct(self, text: str) -> str:
        cleaned = " ".join(text.split())
        cleaned = cleaned[:1].upper() + cleaned[1:]
        if cleaned and cleaned[-1] not in ".!?。！？":
            cleaned += "."
        return cleaned


class DevelopmentEndpoint:
    def detect(self, text: str) -> tuple[bool, str]:
        complete = bool(text.strip()) and text.rstrip().endswith((".", "!", "?", "。", "！", "？"))
        return complete, "terminal_punctuation" if complete else "awaiting_terminal_punctuation"


class DevelopmentAgent:
    def respond(self, text: str) -> str:
        if any("\u3400" <= character <= "\u9fff" for character in text):
            return f"開發模式回覆：我聽到「{text}」"
        return f"Development response: I heard “{text}”"


class DevelopmentTTS:
    sample_rate = 16_000

    def synthesize(self, text: str) -> bytes:
        duration = min(2.0, max(0.25, len(text) * 0.035))
        count = int(self.sample_rate * duration)
        frames = bytearray()
        for index in range(count):
            envelope = min(1.0, index / 320, (count - index) / 320)
            sample = int(0.18 * 32_767 * envelope * math.sin(2 * math.pi * 440 * index / self.sample_rate))
            frames.extend(struct.pack("<h", sample))
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(frames)
        return output.getvalue()
