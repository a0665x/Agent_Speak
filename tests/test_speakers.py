from __future__ import annotations

import stat
from pathlib import Path

import httpx
import pytest

from agent_speak.app import create_app
from agent_speak.config import Settings
from agent_speak.speakers import SpeakerStore, acoustic_vector

from .audio_fixtures import wav_bytes


NOTICE_WORDS = ("not", "authentication")


def test_acoustic_vector_is_deterministic_and_frequency_sensitive() -> None:
    a = acoustic_vector(wav_bytes(frequency=220))
    b = acoustic_vector(wav_bytes(frequency=220))
    c = acoustic_vector(wav_bytes(frequency=1200))

    assert a == pytest.approx(b)
    assert len(a) >= 10
    assert sum(abs(left - right) for left, right in zip(a, c, strict=True)) > 0.5


def test_speaker_store_persists_enrollment_matches_and_deletes_private_files(tmp_path: Path) -> None:
    store = SpeakerStore(tmp_path / "speakers.sqlite3", tmp_path / "samples", max_audio_bytes=100_000, max_audio_seconds=1)
    profile = store.create("Ada", "local test")
    enrolled = store.enroll(profile.id, wav_bytes(frequency=220))

    reopened = SpeakerStore(tmp_path / "speakers.sqlite3", tmp_path / "samples", max_audio_bytes=100_000, max_audio_seconds=1)
    fetched = reopened.get(profile.id)
    matched = reopened.match(wav_bytes(frequency=220), threshold=0.8)
    different = reopened.match(wav_bytes(frequency=1500), threshold=0.8)

    assert enrolled.sample_count == 1
    assert fetched.name == "Ada"
    assert matched.match is not None and matched.match.id == profile.id
    assert matched.score is not None and matched.score >= 0.8
    assert different.match is None
    sample_files = list((tmp_path / "samples" / profile.id).glob("*.wav"))
    assert len(sample_files) == 1

    reopened.delete(profile.id)
    assert reopened.list() == []
    assert not sample_files[0].exists()


def test_speaker_store_uses_owner_only_permissions(tmp_path: Path) -> None:
    database = tmp_path / "private" / "speakers.sqlite3"
    samples = tmp_path / "private" / "samples"
    store = SpeakerStore(database, samples, max_audio_bytes=100_000, max_audio_seconds=1)
    profile = store.create("Private")
    store.enroll(profile.id, wav_bytes())

    sample = next((samples / profile.id).glob("*.wav"))
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    assert stat.S_IMODE(samples.stat().st_mode) == 0o700
    assert stat.S_IMODE((samples / profile.id).stat().st_mode) == 0o700
    assert stat.S_IMODE(sample.stat().st_mode) == 0o600


@pytest.mark.anyio
async def test_speaker_crud_enrollment_and_match_api_use_non_authentication_language(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        empty = await client.get("/api/v1/speakers")
        created = await client.post("/api/v1/speakers", json={"name": "Lin", "notes": "Operator"})
        speaker_id = created.json()["speaker"]["id"]
        enrolled = await client.post(
            f"/api/v1/speakers/{speaker_id}/samples",
            content=wav_bytes(frequency=330),
            headers={"content-type": "audio/wav"},
        )
        matched = await client.post(
            "/api/v1/speakers/match",
            content=wav_bytes(frequency=330),
            headers={"content-type": "audio/wav"},
        )
        fetched = await client.get(f"/api/v1/speakers/{speaker_id}")
        updated = await client.patch(f"/api/v1/speakers/{speaker_id}", json={"name": "Lin Updated", "notes": "Renamed"})
        deleted = await client.delete(f"/api/v1/speakers/{speaker_id}")

    for response in (empty, created, enrolled, matched, fetched, updated):
        notice = response.json()["notice"].lower()
        assert all(word in notice for word in NOTICE_WORDS)
    assert created.status_code == 201
    assert enrolled.json()["speaker"]["sample_count"] == 1
    assert matched.json()["match"]["id"] == speaker_id
    assert updated.json()["speaker"]["name"] == "Lin Updated"
    assert deleted.status_code == 204


@pytest.mark.anyio
async def test_wav_api_is_bounded_and_uses_error_envelope(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime", max_audio_bytes=1000)
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        invalid = await client.post("/api/v1/audio/vad", content=b"not-wave", headers={"content-type": "audio/wav"})
        too_large = await client.post("/api/v1/audio/vad", content=wav_bytes(), headers={"content-type": "audio/wav"})

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_wav"
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "audio_too_large"
