from __future__ import annotations

import io
import math
import struct
import wave


def wav_bytes(*, frequency: float = 440, amplitude: float = 0.3, seconds: float = 0.25, rate: int = 16_000) -> bytes:
    count = int(rate * seconds)
    frames = bytearray()
    for index in range(count):
        sample = int(amplitude * 32_767 * math.sin(2 * math.pi * frequency * index / rate))
        frames.extend(struct.pack("<h", sample))
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)
    return output.getvalue()
