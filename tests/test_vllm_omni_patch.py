from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_voxcpm2_patch_casts_native_tts_to_the_selected_vllm_dtype(tmp_path: Path) -> None:
    target = tmp_path / "voxcpm2_talker.py"
    target.write_text(
        "native = VoxCPM.from_pretrained(model_path, load_denoiser=False, optimize=False)\n"
        "self._tts: nn.Module = native.tts_model.to(self._device)\n"
        "self._side_dtype = self._tts.fusion_concat_proj.weight.dtype\n"
        "feat = tts.audio_vae.encode(audio.to(vae_device), encode_sr).cpu()\n"
        "    def _run_vae_decode(self, feat: torch.Tensor) -> torch.Tensor:\n"
        "        if feat.device.type != current_omni_platform.device_type:\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python",
            str(ROOT / "scripts" / "patch_vllm_omni_voxcpm2.py"),
            "--target",
            str(target),
        ],
        check=True,
    )

    patched = target.read_text(encoding="utf-8")
    assert "native.tts_model.to(self._device, dtype=vllm_config.model_config.dtype)" in patched
    assert "native.tts_model.to(self._device)\n" not in patched
    assert "audio.to(vae_device, dtype=next(tts.audio_vae.parameters()).dtype)" in patched
    assert (
        "    def _run_vae_decode(self, feat: torch.Tensor) -> torch.Tensor:\n"
        "        feat = feat.to(self._side_dtype)\n"
    ) in patched


def test_tts_image_applies_the_guarded_voxcpm2_patch() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY scripts/patch_vllm_omni_voxcpm2.py /tmp/patch_vllm_omni_voxcpm2.py" in dockerfile
    assert "python /tmp/patch_vllm_omni_voxcpm2.py" in dockerfile


def test_voxcpm2_patch_fails_closed_when_pinned_source_changes(tmp_path: Path) -> None:
    target = tmp_path / "voxcpm2_talker.py"
    original = "# upstream adapter changed\n"
    target.write_text(original, encoding="utf-8")

    result = subprocess.run(
        [
            "python",
            str(ROOT / "scripts" / "patch_vllm_omni_voxcpm2.py"),
            "--target",
            str(target),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "refusing to patch unexpected VoxCPM2 adapter" in result.stderr
    assert target.read_text(encoding="utf-8") == original
