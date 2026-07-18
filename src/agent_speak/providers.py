"""Provider interfaces and capability declarations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .schemas import ProviderCapability


class Provider(Protocol):
    capability: ProviderCapability


@runtime_checkable
class VADProvider(Protocol):
    def detect(self, audio: bytes) -> dict[str, object]: ...


@runtime_checkable
class ASRProvider(Protocol):
    def transcribe(self, audio: bytes) -> str: ...


@runtime_checkable
class CorrectionProvider(Protocol):
    def correct(self, text: str) -> str: ...


@runtime_checkable
class EndpointProvider(Protocol):
    def detect(self, text: str) -> tuple[bool, str]: ...


@runtime_checkable
class AgentProvider(Protocol):
    def respond(self, text: str) -> str: ...


@runtime_checkable
class TTSProvider(Protocol):
    def synthesize(self, text: str) -> bytes: ...


DEFAULT_CAPABILITIES = [
    ProviderCapability(stage="vad", name="energy-vad", ready=True, development=False, limitations=[]),
    ProviderCapability(stage="asr", name="deterministic-development-asr", ready=True, development=True, limitations=["Signal-derived fixture text; not speech recognition."]),
    ProviderCapability(stage="correction", name="deterministic-development-correction", ready=True, development=True, limitations=["Whitespace and sentence casing only."]),
    ProviderCapability(stage="endpoint", name="deterministic-development-endpoint", ready=True, development=True, limitations=["Punctuation and text-length heuristic only."]),
    ProviderCapability(stage="agent", name="deterministic-development-agent", ready=True, development=True, limitations=["Template response; no language model inference."]),
    ProviderCapability(stage="tts", name="deterministic-development-tts", ready=True, development=True, limitations=["Synthetic tone WAV; not natural speech."]),
]
