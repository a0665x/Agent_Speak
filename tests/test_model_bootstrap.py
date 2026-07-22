from __future__ import annotations

from pathlib import Path

import pytest

from scripts.bootstrap_models import (
    MODEL_REVISION_MARKER,
    ModelDownloadError,
    ModelSpaceError,
    download_all,
    model_manifest,
    verify_models,
)


def populate_entry(root: Path, model_id: str) -> Path:
    entry = model_manifest()[model_id]
    target = root / entry.target
    target.mkdir(parents=True, exist_ok=True)
    for name in entry.required_files:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"model")
    (target / MODEL_REVISION_MARKER).write_text(entry.revision, encoding="utf-8")
    return target


def test_manifest_pins_all_models_and_excludes_breeze_training_artifacts() -> None:
    manifest = model_manifest()

    assert set(manifest) == {
        "faster-whisper-small",
        "breeze-asr-25",
        "qwen3-asr-1.7b",
        "qwen2.5-correction",
        "piper-zh-cn-huayan-medium",
    }
    assert manifest["faster-whisper-small"].revision == "536b0662742c02347bc0e980a01041f333bce120"
    assert manifest["breeze-asr-25"].revision == "cffe7ccb404d025296a00758d0a33468bec3a9d0"
    assert manifest["qwen3-asr-1.7b"].revision == "7278e1e70fe206f11671096ffdd38061171dd6e5"
    assert manifest["qwen2.5-correction"].revision == "91cad51170dc346986eccefdc2dd33a9da36ead9"
    breeze = manifest["breeze-asr-25"]
    assert "model.safetensors" in breeze.allow_patterns
    assert "optimizer.bin" not in breeze.allow_patterns
    assert "scheduler.bin" not in breeze.allow_patterns
    assert not any(pattern.endswith(".pt") for pattern in breeze.allow_patterns)


def test_cached_verified_models_perform_no_downloads(tmp_path: Path) -> None:
    for model_id in model_manifest():
        populate_entry(tmp_path, model_id)
    calls: list[str] = []

    result = download_all(
        tmp_path,
        free_bytes=100 * 1024**3,
        snapshot_download=lambda **_: calls.append("snapshot"),
        piper_download=lambda *_: calls.append("piper"),
    )

    assert calls == []
    assert result == []
    assert verify_models(tmp_path) == []


def test_downloads_exact_revisions_into_atomic_targets(tmp_path: Path) -> None:
    calls: list[tuple[str, str, tuple[str, ...]]] = []
    manifest = model_manifest()

    def snapshot_download(*, repo_id: str, revision: str, local_dir: Path, allow_patterns: tuple[str, ...]) -> None:
        calls.append((repo_id, revision, allow_patterns))
        entry = next(item for item in manifest.values() if item.repo_id == repo_id)
        local_dir.mkdir(parents=True, exist_ok=True)
        for name in entry.required_files:
            path = local_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"downloaded")

    def piper_download(voice: str, local_dir: Path) -> None:
        assert voice == "zh_CN-huayan-medium"
        entry = manifest["piper-zh-cn-huayan-medium"]
        local_dir.mkdir(parents=True, exist_ok=True)
        for name in entry.required_files:
            (local_dir / name).write_bytes(b"voice")

    downloaded = download_all(
        tmp_path,
        free_bytes=100 * 1024**3,
        snapshot_download=snapshot_download,
        piper_download=piper_download,
    )

    assert set(downloaded) == set(manifest)
    assert {(repo, revision) for repo, revision, _ in calls} == {
        (entry.repo_id, entry.revision)
        for entry in manifest.values()
        if entry.repo_id is not None
    }
    assert verify_models(tmp_path) == []
    assert not list(tmp_path.rglob("*.partial-*"))


def test_preflight_preserves_existing_models_when_space_is_low(tmp_path: Path) -> None:
    existing = tmp_path / "qwen" / "keep.gguf"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"keep")

    with pytest.raises(ModelSpaceError):
        download_all(
            tmp_path,
            free_bytes=1,
            snapshot_download=lambda **_: None,
            piper_download=lambda *_: None,
        )

    assert existing.read_bytes() == b"keep"
    assert not list(tmp_path.rglob("*.partial-*"))


def test_failure_cleans_only_current_partial_and_preserves_other_files(tmp_path: Path) -> None:
    preserved = tmp_path / "unrelated" / "keep.bin"
    preserved.parent.mkdir()
    preserved.write_bytes(b"keep")

    def fail_download(*, local_dir: Path, **_: object) -> None:
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "partial.bin").write_bytes(b"partial")
        raise RuntimeError("network failed")

    with pytest.raises(ModelDownloadError) as captured:
        download_all(
            tmp_path,
            free_bytes=100 * 1024**3,
            snapshot_download=fail_download,
            piper_download=lambda *_: None,
        )

    assert captured.value.model_id == "faster-whisper-small"
    assert preserved.read_bytes() == b"keep"
    assert not list(tmp_path.rglob("*.partial-*"))


def test_verify_rejects_zero_length_required_file_and_wrong_revision(tmp_path: Path) -> None:
    target = populate_entry(tmp_path, "breeze-asr-25")
    (target / "model.safetensors").write_bytes(b"")
    (populate_entry(tmp_path, "qwen3-asr-1.7b") / MODEL_REVISION_MARKER).write_text(
        "wrong", encoding="utf-8"
    )

    missing = verify_models(tmp_path)

    assert "breeze-asr-25" in missing
    assert "qwen3-asr-1.7b" in missing
