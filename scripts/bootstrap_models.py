"""Idempotently populate the private model volume for realtime workers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Any


QWEN_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
QWEN_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
WHISPER_FILES = ("model.bin", "config.json", "tokenizer.json")


def bootstrap_models(
    models_root: Path,
    *,
    asr_model: str,
    download_model: Callable[..., Any],
    hf_download: Callable[..., Any],
) -> None:
    root = models_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    configured = Path(asr_model).expanduser()
    whisper_cached = configured.is_dir() and all((configured / name).is_file() for name in WHISPER_FILES)
    if not whisper_cached:
        download_model(asr_model, cache_dir=str(root / "huggingface" / "hub"))

    qwen_dir = root / "qwen"
    qwen_path = qwen_dir / QWEN_FILE
    if not qwen_path.is_file() or qwen_path.stat().st_size == 0:
        hf_download(
            repo_id=QWEN_REPO,
            filename=QWEN_FILE,
            local_dir=qwen_dir,
        )
    if not qwen_path.is_file() or qwen_path.stat().st_size == 0:
        raise RuntimeError("Qwen model bootstrap did not produce a non-empty artifact")


def main() -> None:
    if os.getenv("AGENT_SPEAK_SKIP_MODEL_BOOTSTRAP") == "1":
        print("MODEL_BOOTSTRAP_SKIPPED")
        return
    root = Path(os.getenv("AGENT_SPEAK_MODELS_ROOT", "/app/models"))
    if root.resolve() != Path("/app/models"):
        raise RuntimeError("model bootstrap may write only beneath /app/models")
    from faster_whisper.utils import download_model
    from huggingface_hub import hf_hub_download

    bootstrap_models(
        root,
        asr_model=os.getenv("AGENT_SPEAK_ASR_MODEL", "small"),
        download_model=download_model,
        hf_download=hf_hub_download,
    )
    print("MODEL_BOOTSTRAP_OK")


if __name__ == "__main__":
    main()
