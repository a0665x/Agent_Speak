"""Stable public identifiers for selectable inference models."""

from __future__ import annotations

from typing import Literal


ASRModelId = Literal[
    "faster-whisper-small",
    "breeze-asr-25",
    "qwen3-asr-1.7b",
]
CorrectionModelId = Literal["qwen2.5-correction", "disabled"]

DEFAULT_ASR_MODEL: ASRModelId = "qwen3-asr-1.7b"
DEFAULT_CORRECTION_MODEL: CorrectionModelId = "qwen2.5-correction"
