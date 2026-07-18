"""Private speaker-profile persistence and deterministic acoustic convenience matching."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np

from .audio import decode_wav
from .errors import PlatformError
from .schemas import SpeakerMatch, SpeakerProfile


SPEAKER_NOTICE = "Convenience identification only; this is not biometric authentication."


def acoustic_vector(payload: bytes, *, max_bytes: int = 8 * 1024 * 1024, max_seconds: float = 30) -> list[float]:
    audio = decode_wav(payload, max_bytes=max_bytes, max_seconds=max_seconds, stage="speaker")
    samples = audio.samples
    if samples.size < 32:
        raise PlatformError("sample_too_short", "Speaker sample is too short", stage="speaker")
    windowed = samples * np.hanning(samples.size).astype(np.float32)
    spectrum = np.square(np.abs(np.fft.rfft(windowed)))
    frequencies = np.fft.rfftfreq(samples.size, 1 / audio.sample_rate)
    edges = np.linspace(80, min(4_000, audio.sample_rate / 2), 17)
    bands = np.array(
        [float(spectrum[(frequencies >= low) & (frequencies < high)].sum()) for low, high in zip(edges[:-1], edges[1:], strict=True)],
        dtype=np.float64,
    )
    total = float(bands.sum())
    if total <= 1e-12:
        raise PlatformError("sample_has_no_signal", "Speaker sample has no usable signal", stage="speaker")
    bands /= total
    zcr = float(np.mean(np.signbit(samples[1:]) != np.signbit(samples[:-1])))
    centroid = float((frequencies * spectrum).sum() / max(float(spectrum.sum()), 1e-12) / (audio.sample_rate / 2))
    vector = np.concatenate((bands, np.array([zcr, centroid], dtype=np.float64)))
    norm = float(np.linalg.norm(vector))
    return (vector / norm).round(8).tolist()


class SpeakerStore:
    def __init__(self, database: Path, sample_dir: Path, *, max_audio_bytes: int, max_audio_seconds: float) -> None:
        self.database = database
        self.sample_dir = sample_dir
        self.max_audio_bytes = max_audio_bytes
        self.max_audio_seconds = max_audio_seconds
        database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        database.parent.chmod(0o700)
        sample_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        sample_dir.chmod(0o700)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS speakers (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS samples (
                    id TEXT PRIMARY KEY, speaker_id TEXT NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
                    path TEXT NOT NULL, vector TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )
        self.database.chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _profile(row: sqlite3.Row, count: int) -> SpeakerProfile:
        return SpeakerProfile(
            id=row["id"],
            name=row["name"],
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            sample_count=count,
        )

    def create(self, name: str, notes: str = "") -> SpeakerProfile:
        speaker_id = uuid4().hex
        created = datetime.now(timezone.utc)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO speakers(id, name, notes, created_at) VALUES (?, ?, ?, ?)",
                (speaker_id, name, notes, created.isoformat()),
            )
        return SpeakerProfile(id=speaker_id, name=name, notes=notes, created_at=created, sample_count=0)

    def get(self, speaker_id: str) -> SpeakerProfile:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM speakers WHERE id = ?", (speaker_id,)).fetchone()
            if row is None:
                raise PlatformError("speaker_not_found", "Speaker profile not found", status_code=404, stage="speaker")
            count = connection.execute("SELECT COUNT(*) FROM samples WHERE speaker_id = ?", (speaker_id,)).fetchone()[0]
        return self._profile(row, count)

    def update(self, speaker_id: str, name: str, notes: str) -> SpeakerProfile:
        self.get(speaker_id)
        with self._connect() as connection:
            connection.execute("UPDATE speakers SET name = ?, notes = ? WHERE id = ?", (name, notes, speaker_id))
        return self.get(speaker_id)

    def list(self) -> list[SpeakerProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT s.*, COUNT(x.id) AS sample_count FROM speakers s LEFT JOIN samples x ON x.speaker_id = s.id GROUP BY s.id ORDER BY s.created_at"
            ).fetchall()
        return [self._profile(row, row["sample_count"]) for row in rows]

    def enroll(self, speaker_id: str, payload: bytes) -> SpeakerProfile:
        self.get(speaker_id)
        vector = acoustic_vector(payload, max_bytes=self.max_audio_bytes, max_seconds=self.max_audio_seconds)
        sample_id = uuid4().hex
        directory = self.sample_dir / speaker_id
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        path = directory / f"{sample_id}.wav"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as sample_file:
            sample_file.write(payload)
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO samples(id, speaker_id, path, vector, created_at) VALUES (?, ?, ?, ?, ?)",
                    (sample_id, speaker_id, str(path), json.dumps(vector), datetime.now(timezone.utc).isoformat()),
                )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self.get(speaker_id)

    def match(self, payload: bytes, *, threshold: float = 0.86) -> SpeakerMatch:
        query = np.array(
            acoustic_vector(payload, max_bytes=self.max_audio_bytes, max_seconds=self.max_audio_seconds), dtype=np.float64
        )
        best_id: str | None = None
        best_score: float | None = None
        with self._connect() as connection:
            rows = connection.execute("SELECT speaker_id, vector FROM samples").fetchall()
        by_speaker: dict[str, list[np.ndarray]] = {}
        for row in rows:
            by_speaker.setdefault(row["speaker_id"], []).append(np.array(json.loads(row["vector"]), dtype=np.float64))
        for speaker_id, vectors in by_speaker.items():
            reference = np.mean(vectors, axis=0)
            reference /= max(float(np.linalg.norm(reference)), 1e-12)
            score = float(np.dot(query, reference))
            if best_score is None or score > best_score:
                best_id, best_score = speaker_id, score
        match = self.get(best_id) if best_id is not None and best_score is not None and best_score >= threshold else None
        return SpeakerMatch(match=match, score=round(best_score, 6) if best_score is not None else None, threshold=threshold)

    def delete(self, speaker_id: str) -> None:
        self.get(speaker_id)
        with self._connect() as connection:
            connection.execute("DELETE FROM speakers WHERE id = ?", (speaker_id,))
        directory = self.sample_dir / speaker_id
        if directory.is_dir():
            shutil.rmtree(directory)
