from __future__ import annotations

import io
import shutil
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

from agent_speak.config import Settings
from agent_speak.pipeline import ProviderSet
from agent_speak.production import FasterWhisperASR, PiperTTS
from .audio_fixtures import wav_bytes


class FakeWhisperModel:
    def __init__(self) -> None:
        self.audio_header = b""
        self.kwargs: dict[str, object] = {}

    def transcribe(self, audio: io.BytesIO, **kwargs: object):
        self.audio_header = audio.read(4)
        self.kwargs = kwargs
        return iter([SimpleNamespace(text=" 你好，這是真實辨識。 ")]), SimpleNamespace(language="zh")


class FakePiperVoice:
    def __init__(self) -> None:
        self.text = ""

    def synthesize_wav(self, text: str, wav_file: wave.Wave_write) -> None:
        self.text = text
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22_050)
        wav_file.writeframes(b"\x01\x00" * 2_205)


def test_faster_whisper_provider_returns_recognized_text_and_passes_language() -> None:
    model = FakeWhisperModel()
    provider = FasterWhisperASR(
        model_name="small",
        language="zh",
        compute_type="int8",
        model_factory=lambda *args, **kwargs: model,
    )

    transcript = provider.transcribe(wav_bytes())

    assert transcript == "你好，這是真實辨識。"
    assert model.audio_header == b"RIFF"
    assert model.kwargs["language"] == "zh"
    assert model.kwargs["vad_filter"] is True


def test_piper_provider_returns_spoken_pcm_wav(tmp_path: Path) -> None:
    model_path = tmp_path / "voice.onnx"
    config_path = tmp_path / "voice.onnx.json"
    model_path.write_bytes(b"model")
    config_path.write_text("{}", encoding="utf-8")
    voice = FakePiperVoice()
    provider = PiperTTS(model_path=model_path, voice_factory=lambda *args, **kwargs: voice)

    payload = provider.synthesize("你好，這不是提示音。")

    with wave.open(io.BytesIO(payload), "rb") as wav_file:
        assert wav_file.getframerate() == 22_050
        assert wav_file.getnframes() == 2_205
    assert voice.text == "你好，這不是提示音。"


def test_default_provider_set_uses_real_asr_and_tts(tmp_path: Path) -> None:
    model_path = tmp_path / "voice.onnx"
    model_path.write_bytes(b"model")
    (tmp_path / "voice.onnx.json").write_text("{}", encoding="utf-8")
    settings = Settings(tts_model_path=model_path)

    providers = ProviderSet.configured(settings, vad=object())
    capabilities = {item.stage: item for item in providers.capabilities()}

    assert isinstance(providers.asr, FasterWhisperASR)
    assert isinstance(providers.tts, PiperTTS)
    assert capabilities["asr"].development is False
    assert capabilities["tts"].development is False
    assert capabilities["asr"].name == "faster-whisper-small"
    assert capabilities["tts"].name == "piper-voice"
    assert capabilities["tts"].limitations == ["Piper local speech synthesis."]


def test_asr_capability_is_not_ready_until_model_is_available(tmp_path: Path) -> None:
    model_path = tmp_path / "cached-model"
    model_path.mkdir()
    (model_path / "model.bin").write_bytes(b"model")
    (model_path / "config.json").write_text("{}", encoding="utf-8")
    settings = Settings(tts_model_path=tmp_path / "missing-voice.onnx")
    providers = ProviderSet.configured(settings, vad=object())

    def unavailable_resolver(_: str) -> Path:
        raise RuntimeError("cache inspection failed")

    providers.asr._local_model_resolver = unavailable_resolver  # type: ignore[attr-defined]

    unavailable = {item.stage: item for item in providers.capabilities()}["asr"]
    assert unavailable.ready is False
    assert "not cached" in unavailable.limitations[0].lower()

    providers.asr._local_model_resolver = lambda _: model_path  # type: ignore[attr-defined]
    incomplete = {item.stage: item for item in providers.capabilities()}["asr"]
    assert incomplete.ready is False

    (model_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    available = {item.stage: item for item in providers.capabilities()}["asr"]
    assert available.ready is True


def test_setup_loads_dotenv_before_resolving_relative_model_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    source_script = Path(__file__).parents[1] / "scripts" / "setup.sh"
    shutil.copy2(source_script, scripts / "setup.sh")

    python = project / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"-m\" && \"$2\" == \"piper.download_voices\" ]]; then exit 91; fi\n"
        "if [[ \"$1\" == \"--version\" ]]; then echo 'Python 3.11.test'; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    model = project / "custom models" / "voice.onnx"
    model.parent.mkdir()
    model.write_bytes(b"model")
    Path(f"{model}.json").write_text("{}", encoding="utf-8")
    (project / ".env").write_text(
        "AGENT_SPEAK_TTS_MODEL_PATH='custom models/voice.onnx'\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(scripts / "setup.sh")],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "SETUP_OK" in result.stdout
