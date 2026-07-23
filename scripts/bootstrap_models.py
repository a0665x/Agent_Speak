"""Pinned, explicit and atomic preparation of private speech-model storage."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal


MODEL_REVISION_MARKER = ".agent-speak-revision"
SAFETY_RESERVE_BYTES = 8 * 1024**3
TEMPORARY_OVERHEAD_RATIO = 1.15


@dataclass(frozen=True, slots=True)
class ModelManifestEntry:
    model_id: str
    target: Path
    revision: str
    estimated_bytes: int
    required_files: tuple[str, ...]
    repo_id: str | None = None
    allow_patterns: tuple[str, ...] = ()
    kind: Literal["huggingface", "piper"] = "huggingface"
    voice: str | None = None


class ModelSpaceError(RuntimeError):
    pass


class ModelDownloadError(RuntimeError):
    def __init__(self, model_id: str, message: str) -> None:
        super().__init__(message)
        self.model_id = model_id


def model_manifest() -> dict[str, ModelManifestEntry]:
    entries = (
        ModelManifestEntry(
            model_id="faster-whisper-small",
            repo_id="Systran/faster-whisper-small",
            revision="536b0662742c02347bc0e980a01041f333bce120",
            target=Path("asr/faster-whisper-small"),
            estimated_bytes=500_000_000,
            allow_patterns=("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"),
            required_files=("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"),
        ),
        ModelManifestEntry(
            model_id="breeze-asr-25",
            repo_id="MediaTek-Research/Breeze-ASR-25",
            revision="cffe7ccb404d025296a00758d0a33468bec3a9d0",
            target=Path("asr/breeze-asr-25"),
            estimated_bytes=3_200_000_000,
            allow_patterns=(
                "added_tokens.json",
                "config.json",
                "generation_config.json",
                "merges.txt",
                "model.safetensors",
                "normalizer.json",
                "preprocessor_config.json",
                "special_tokens_map.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.json",
            ),
            required_files=(
                "config.json",
                "model.safetensors",
                "preprocessor_config.json",
                "tokenizer.json",
                "tokenizer_config.json",
            ),
        ),
        ModelManifestEntry(
            model_id="qwen3-asr-1.7b",
            repo_id="Qwen/Qwen3-ASR-1.7B",
            revision="7278e1e70fe206f11671096ffdd38061171dd6e5",
            target=Path("asr/qwen3-asr-1.7b"),
            estimated_bytes=4_800_000_000,
            allow_patterns=(
                "chat_template.json",
                "config.json",
                "generation_config.json",
                "merges.txt",
                "model-00001-of-00002.safetensors",
                "model-00002-of-00002.safetensors",
                "model.safetensors.index.json",
                "preprocessor_config.json",
                "tokenizer_config.json",
                "vocab.json",
            ),
            required_files=(
                "config.json",
                "model-00001-of-00002.safetensors",
                "model-00002-of-00002.safetensors",
                "model.safetensors.index.json",
                "preprocessor_config.json",
                "tokenizer_config.json",
            ),
        ),
        ModelManifestEntry(
            model_id="qwen2.5-correction",
            repo_id="Qwen/Qwen2.5-1.5B-Instruct-GGUF",
            revision="91cad51170dc346986eccefdc2dd33a9da36ead9",
            target=Path("qwen"),
            estimated_bytes=1_100_000_000,
            allow_patterns=("qwen2.5-1.5b-instruct-q4_k_m.gguf",),
            required_files=("qwen2.5-1.5b-instruct-q4_k_m.gguf",),
        ),
        ModelManifestEntry(
            model_id="voxcpm2",
            repo_id="openbmb/VoxCPM2",
            revision="bffb3df5a29440629464e5e839f4d214c8714c3d",
            target=Path("tts/voxcpm2"),
            estimated_bytes=9_600_000_000,
            allow_patterns=(
                "audiovae.pth",
                "config.json",
                "model.safetensors",
                "special_tokens_map.json",
                "tokenization_voxcpm2.py",
                "tokenizer.json",
                "tokenizer_config.json",
            ),
            required_files=(
                "audiovae.pth",
                "config.json",
                "model.safetensors",
                "special_tokens_map.json",
                "tokenization_voxcpm2.py",
                "tokenizer.json",
                "tokenizer_config.json",
            ),
        ),
        ModelManifestEntry(
            model_id="piper-zh-cn-huayan-medium",
            target=Path("piper"),
            revision="piper-voices-2023-11-14",
            estimated_bytes=70_000_000,
            required_files=(
                "zh_CN-huayan-medium.onnx",
                "zh_CN-huayan-medium.onnx.json",
            ),
            kind="piper",
            voice="zh_CN-huayan-medium",
        ),
    )
    return {entry.model_id: entry for entry in entries}


def _safe_target(root: Path, relative: Path) -> Path:
    resolved_root = root.resolve()
    target = (resolved_root / relative).resolve()
    if not target.is_relative_to(resolved_root) or target == resolved_root:
        raise RuntimeError("model target escapes the configured model root")
    return target


def _required_files_ready(target: Path, entry: ModelManifestEntry) -> bool:
    return all(
        (target / name).is_file() and (target / name).stat().st_size > 0
        for name in entry.required_files
    )


def _entry_ready(root: Path, entry: ModelManifestEntry) -> bool:
    target = _safe_target(root, entry.target)
    marker = target / MODEL_REVISION_MARKER
    if not _required_files_ready(target, entry) or not marker.is_file():
        return False
    try:
        return marker.read_text(encoding="utf-8").strip() == entry.revision
    except OSError:
        return False


def verify_models(models_root: Path) -> list[str]:
    root = Path(models_root).resolve()
    return [
        model_id
        for model_id, entry in model_manifest().items()
        if not _entry_ready(root, entry)
    ]


def _default_snapshot_download(**kwargs: object) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(**kwargs)


def _default_piper_download(voice: str, local_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "piper.download_voices",
            voice,
            "--download-dir",
            str(local_dir),
        ],
        check=True,
    )


def _adopt_complete_legacy_targets(root: Path) -> None:
    for entry in model_manifest().values():
        target = _safe_target(root, entry.target)
        marker = target / MODEL_REVISION_MARKER
        if _required_files_ready(target, entry) and not marker.exists():
            marker.write_text(entry.revision, encoding="utf-8")
        if _entry_ready(root, entry):
            _make_runtime_readable(target)


def _make_runtime_readable(target: Path) -> None:
    """Keep Docker-created private weights readable/manageable by the host owner."""
    for directory, directory_names, file_names in os.walk(target):
        Path(directory).chmod(0o755)
        for name in directory_names:
            path = Path(directory) / name
            if not path.is_symlink():
                path.chmod(0o755)
        for name in file_names:
            path = Path(directory) / name
            if not path.is_symlink():
                path.chmod(0o644)


def download_all(
    models_root: Path,
    *,
    free_bytes: int | None = None,
    snapshot_download: Callable[..., object] = _default_snapshot_download,
    piper_download: Callable[[str, Path], object] = _default_piper_download,
) -> list[str]:
    root = Path(models_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    _adopt_complete_legacy_targets(root)
    manifest = model_manifest()
    missing = [entry for entry in manifest.values() if not _entry_ready(root, entry)]
    if not missing:
        return []

    required = int(sum(entry.estimated_bytes for entry in missing) * TEMPORARY_OVERHEAD_RATIO) + SAFETY_RESERVE_BYTES
    available = free_bytes if free_bytes is not None else shutil.disk_usage(root).free
    if available < required:
        raise ModelSpaceError(
            f"insufficient model storage: need {required / 1024**3:.1f} GiB including reserve; "
            f"have {available / 1024**3:.1f} GiB"
        )

    downloaded: list[str] = []
    for entry in missing:
        target = _safe_target(root, entry.target)
        if target.exists():
            raise ModelDownloadError(
                entry.model_id,
                f"existing incomplete model target blocks atomic preparation: {entry.model_id}",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f"{target.name}.partial-{uuid.uuid4().hex}")
        try:
            partial.mkdir(mode=0o700)
            if entry.kind == "piper":
                assert entry.voice is not None
                piper_download(entry.voice, partial)
            else:
                assert entry.repo_id is not None
                snapshot_download(
                    repo_id=entry.repo_id,
                    revision=entry.revision,
                    local_dir=partial,
                    allow_patterns=entry.allow_patterns,
                )
            (partial / MODEL_REVISION_MARKER).write_text(entry.revision, encoding="utf-8")
            if not _entry_ready_from_target(partial, entry):
                raise RuntimeError("download did not produce all required inference artifacts")
            _make_runtime_readable(partial)
            partial.rename(target)
            downloaded.append(entry.model_id)
        except Exception as exc:
            if partial.exists():
                shutil.rmtree(partial)
            raise ModelDownloadError(
                entry.model_id,
                f"model preparation failed: {entry.model_id}",
            ) from exc
    return downloaded


def _entry_ready_from_target(target: Path, entry: ModelManifestEntry) -> bool:
    marker = target / MODEL_REVISION_MARKER
    return (
        _required_files_ready(target, entry)
        and marker.is_file()
        and marker.read_text(encoding="utf-8").strip() == entry.revision
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--download-all", action="store_true")
    args = parser.parse_args()

    root = Path(os.getenv("AGENT_SPEAK_MODELS_ROOT", "/app/models")).resolve()
    if root != Path("/app/models"):
        raise RuntimeError("model preparation may write only beneath /app/models")
    if args.verify:
        missing = verify_models(root)
        if missing:
            print(f"MODEL_VERIFY_MISSING ids={','.join(missing)} run='./run.sh --models'", file=sys.stderr)
            raise SystemExit(3)
        print("MODEL_VERIFY_OK")
        return

    downloaded = download_all(root)
    print(f"MODEL_DOWNLOAD_OK downloaded={','.join(downloaded) if downloaded else 'none'}")


if __name__ == "__main__":
    main()
