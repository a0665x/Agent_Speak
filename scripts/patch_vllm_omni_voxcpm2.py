#!/usr/bin/env python3
"""Apply the pinned VoxCPM2 FP16 side-model compatibility patch."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_TARGET = Path(
    "/usr/local/lib/python3.12/site-packages/"
    "vllm_omni/model_executor/models/voxcpm2/voxcpm2_talker.py"
)
PATCHES = (
    (
        "self._tts: nn.Module = native.tts_model.to(self._device)",
        "self._tts: nn.Module = native.tts_model.to("
        "self._device, dtype=vllm_config.model_config.dtype)",
    ),
    (
        "audio.to(vae_device)",
        "audio.to(vae_device, dtype=next(tts.audio_vae.parameters()).dtype)",
    ),
    (
        "    def _run_vae_decode(self, feat: torch.Tensor) -> torch.Tensor:\n"
        "        if feat.device.type != current_omni_platform.device_type:",
        "    def _run_vae_decode(self, feat: torch.Tensor) -> torch.Tensor:\n"
        "        feat = feat.to(self._side_dtype)\n"
        "        if feat.device.type != current_omni_platform.device_type:",
    ),
)


def patch(target: Path) -> None:
    source = target.read_text(encoding="utf-8")
    for old, new in PATCHES:
        if new in source:
            continue
        if source.count(old) != 1:
            raise SystemExit(
                f"refusing to patch unexpected VoxCPM2 adapter at {target}: "
                f"expected one pinned source match, found {source.count(old)}"
            )
        source = source.replace(old, new, 1)
    target.write_text(source, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    patch(args.target)


if __name__ == "__main__":
    main()
