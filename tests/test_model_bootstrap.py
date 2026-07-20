from pathlib import Path

from scripts.bootstrap_models import bootstrap_models


def test_cached_models_perform_no_downloads(tmp_path: Path) -> None:
    whisper = tmp_path / "whisper"
    whisper.mkdir()
    for name in ("model.bin", "config.json", "tokenizer.json"):
        (whisper / name).write_bytes(b"cached")
    qwen = tmp_path / "qwen" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    qwen.parent.mkdir()
    qwen.write_bytes(b"cached")
    calls: list[str] = []
    bootstrap_models(
        tmp_path,
        asr_model=str(whisper),
        download_model=lambda *args, **kwargs: calls.append("asr"),
        hf_download=lambda *args, **kwargs: calls.append("qwen"),
    )
    assert calls == []


def test_missing_models_download_exact_qwen_artifact(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def download_model(name: str, **_: object) -> str:
        target = tmp_path / "whisper"
        target.mkdir()
        for filename in ("model.bin", "config.json", "tokenizer.json"):
            (target / filename).write_bytes(b"model")
        return str(target)

    def hf_download(*, repo_id: str, filename: str, local_dir: Path, **_: object) -> str:
        calls.append((repo_id, filename))
        local_dir.mkdir(parents=True, exist_ok=True)
        target = local_dir / filename
        target.write_bytes(b"qwen")
        return str(target)

    bootstrap_models(
        tmp_path,
        asr_model="small",
        download_model=download_model,
        hf_download=hf_download,
    )
    assert calls == [("Qwen/Qwen2.5-1.5B-Instruct-GGUF", "qwen2.5-1.5b-instruct-q4_k_m.gguf")]
