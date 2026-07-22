from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from agent_speak.asr_providers import BreezeASR, Qwen3ASR
from agent_speak.errors import PlatformError
from .audio_fixtures import wav_bytes


class FakeBreezeProcessor:
    def __init__(self, text: str = "今天 deploy 新的 API") -> None:
        self.text = text
        self.samples: np.ndarray | None = None
        self.sample_rate: int | None = None
        self.decoded: object | None = None

    def __call__(self, samples: np.ndarray, *, sampling_rate: int, return_tensors: str) -> dict[str, object]:
        self.samples = samples
        self.sample_rate = sampling_rate
        assert return_tensors == "pt"
        return {"input_features": "features"}

    def batch_decode(self, generated: object, *, skip_special_tokens: bool) -> list[str]:
        self.decoded = generated
        assert skip_special_tokens is True
        return [f"  {self.text}  "]


class FakeBreezeModel:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.generate_kwargs: dict[str, object] = {}

    def generate(self, **kwargs: object) -> list[str]:
        self.generate_kwargs = kwargs
        if self.failure is not None:
            raise self.failure
        return ["tokens"]


class FakeQwenModel:
    def __init__(self, text: str = "請 review 這個 patch", *, failure: Exception | None = None) -> None:
        self.text = text
        self.failure = failure
        self.audio: tuple[np.ndarray, int] | None = None
        self.requested_language: str | None = None

    def transcribe(self, *, audio: tuple[np.ndarray, int], language: str | None) -> list[SimpleNamespace]:
        self.audio = audio
        self.requested_language = language
        if self.failure is not None:
            raise self.failure
        return [SimpleNamespace(text=f"  {self.text}  ")]


def test_breeze_adapter_decodes_resamples_pcm_wav_and_returns_text(tmp_path: Path) -> None:
    processor = FakeBreezeProcessor()
    model = FakeBreezeModel()
    provider = BreezeASR(
        model_path=tmp_path / "breeze",
        accelerator="cpu",
        processor_factory=lambda **_: processor,
        model_factory=lambda **_: model,
    )

    transcript = provider.transcribe(wav_bytes(rate=8_000), language="zh")

    assert transcript == "今天 deploy 新的 API"
    assert processor.sample_rate == 16_000
    assert processor.samples is not None
    assert processor.samples.dtype == np.float32
    assert len(processor.samples) == 4_000
    assert model.generate_kwargs == {"input_features": "features", "language": "zh"}


@pytest.mark.parametrize(
    ("language", "expected"),
    [(None, None), ("auto", None), ("zh", "Chinese"), ("en", "English"), ("ja", "Japanese"), ("ko", "Korean")],
)
def test_qwen_adapter_maps_language_and_returns_first_result(
    tmp_path: Path,
    language: str | None,
    expected: str | None,
) -> None:
    model = FakeQwenModel()
    provider = Qwen3ASR(
        model_path=tmp_path / "qwen3",
        accelerator="cpu",
        model_factory=lambda **_: model,
    )

    assert provider.transcribe(wav_bytes(rate=48_000), language=language) == "請 review 這個 patch"
    assert model.requested_language == expected
    assert model.audio is not None
    assert model.audio[1] == 16_000
    assert model.audio[0].dtype == np.float32
    assert len(model.audio[0]) == 4_000


@pytest.mark.parametrize(
    "factory",
    [
        lambda path: BreezeASR(
            model_path=path,
            accelerator="cpu",
            processor_factory=lambda **_: FakeBreezeProcessor(),
            model_factory=lambda **_: FakeBreezeModel(),
        ),
        lambda path: Qwen3ASR(
            model_path=path,
            accelerator="cpu",
            model_factory=lambda **_: FakeQwenModel(),
        ),
    ],
)
def test_adapters_reject_invalid_wav_without_loading_model(tmp_path: Path, factory: object) -> None:
    provider = factory(tmp_path / "model")  # type: ignore[operator]

    with pytest.raises(PlatformError) as captured:
        provider.transcribe(b"not a wav", language="zh")

    assert captured.value.code == "invalid_wav"
    assert captured.value.stage == "asr"


@pytest.mark.parametrize("provider_kind", ["breeze", "qwen"])
def test_adapters_map_empty_output_to_bounded_error(tmp_path: Path, provider_kind: str) -> None:
    if provider_kind == "breeze":
        provider = BreezeASR(
            model_path=tmp_path / "breeze",
            accelerator="cpu",
            processor_factory=lambda **_: FakeBreezeProcessor(text=""),
            model_factory=lambda **_: FakeBreezeModel(),
        )
    else:
        provider = Qwen3ASR(
            model_path=tmp_path / "qwen",
            accelerator="cpu",
            model_factory=lambda **_: FakeQwenModel(text=""),
        )

    with pytest.raises(PlatformError) as captured:
        provider.transcribe(wav_bytes(), language="zh")

    assert captured.value.code == "no_transcript"
    assert captured.value.status_code == 422
    assert captured.value.stage == "asr"


@pytest.mark.parametrize("provider_kind", ["breeze", "qwen"])
def test_adapters_hide_provider_exception_details(tmp_path: Path, provider_kind: str) -> None:
    if provider_kind == "breeze":
        provider = BreezeASR(
            model_path=tmp_path / "secret-breeze-path",
            accelerator="cpu",
            processor_factory=lambda **_: FakeBreezeProcessor(),
            model_factory=lambda **_: FakeBreezeModel(failure=RuntimeError("secret-breeze-path")),
        )
    else:
        provider = Qwen3ASR(
            model_path=tmp_path / "secret-qwen-path",
            accelerator="cpu",
            model_factory=lambda **_: FakeQwenModel(failure=RuntimeError("secret-qwen-path")),
        )

    with pytest.raises(PlatformError) as captured:
        provider.transcribe(wav_bytes(), language="zh")

    assert captured.value.code == "asr_failed"
    assert captured.value.status_code == 500
    assert captured.value.retryable is True
    assert "secret" not in captured.value.message


def test_qwen_warm_is_idempotent_and_close_allows_reload(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def factory(**kwargs: object) -> FakeQwenModel:
        calls.append(kwargs)
        return FakeQwenModel()

    provider = Qwen3ASR(model_path=tmp_path / "qwen", accelerator="cpu", model_factory=factory)
    provider.warm()
    provider.warm()
    provider.close()
    provider.warm()

    assert len(calls) == 2
    assert calls[0]["model_path"] == tmp_path / "qwen"
    assert calls[0]["device"] == "cpu"
