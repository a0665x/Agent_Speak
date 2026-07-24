from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

import httpx

from .prompt import PromptPacket


@dataclass(frozen=True)
class CandidateResult:
    output_path: Path
    safe_metadata: Mapping[str, object]


class ImageCandidateProvider(Protocol):
    def edit(self, packet: PromptPacket, output_path: Path) -> CandidateResult:
        """Generate one opaque candidate without publication authority."""


class GptImageProvider:
    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max attempts must be positive")
        self._client = client or httpx.Client(timeout=120)
        self._max_attempts = max_attempts

    def edit(self, packet: PromptPacket, output_path: Path) -> CandidateResult:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for live generation")
        for image in packet.images:
            if not image.path.is_file():
                raise ValueError(f"missing provider input: {image.path}")
        started = time.monotonic()
        response: httpx.Response | None = None
        for attempt in range(1, self._max_attempts + 1):
            files = [
                (
                    "image[]",
                    (image.path.name, image.path.read_bytes(), "image/png"),
                )
                for image in packet.images
            ]
            response = self._client.post(
                "https://api.openai.com/v1/images/edits",
                headers={"Authorization": f"Bearer {api_key}"},
                data={
                    "model": "gpt-image-2",
                    "prompt": packet.text,
                    "input_fidelity": "high",
                    "output_format": "png",
                    "size": f"{packet.canvas[0]}x{packet.canvas[1]}",
                    "n": "1",
                },
                files=files,
            )
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt == self._max_attempts:
                break
        assert response is not None
        if response.status_code >= 400:
            raise RuntimeError(
                f"GPT Image request failed with HTTP {response.status_code}"
            )
        payload = response.json()
        try:
            encoded = payload["data"][0]["b64_json"]
            content = base64.b64decode(encoded, validate=True)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("GPT Image response did not contain PNG bytes") from error
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        return CandidateResult(
            output_path=output_path,
            safe_metadata={
                "provider": "openai",
                "model": "gpt-image-2",
                "request_id": response.headers.get("x-request-id"),
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            },
        )

