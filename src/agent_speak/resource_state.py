"""Atomic, bounded persistence for privacy-safe resource state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .resource_types import ResourceSnapshot


class ResourceStateError(ValueError):
    """Raised when persisted resource state is missing or malformed."""


class ResourceStateStore:
    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = 64 * 1024,
    ) -> None:
        self.path = path
        self.max_bytes = max_bytes

    def write(self, snapshot: ResourceSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        encoded = json.dumps(
            snapshot.to_dict(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(encoded) > self.max_bytes:
            raise ResourceStateError("resource state exceeds byte limit")

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                os.chmod(temporary_path, 0o600)
                temporary.write(encoded)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
            self.path.chmod(0o600)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def read(self) -> ResourceSnapshot:
        try:
            size = self.path.stat().st_size
            if size > self.max_bytes:
                raise ResourceStateError("resource state exceeds byte limit")
            payload = self.path.read_bytes()
            if len(payload) > self.max_bytes:
                raise ResourceStateError("resource state exceeds byte limit")
            decoded = json.loads(payload)
            return ResourceSnapshot.from_dict(decoded)
        except ResourceStateError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ResourceStateError("invalid resource state") from exc
