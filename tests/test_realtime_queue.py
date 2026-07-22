import pytest

from agent_speak.realtime_queue import (
    ASRJob,
    ASRScheduler,
    QueueClosed,
    QueueFull,
    TextJob,
    TextScheduler,
)


@pytest.mark.anyio
async def test_final_precedes_partial_and_new_partial_replaces_old_generation() -> None:
    queue = ASRScheduler(max_finals=2, max_partials=2)
    inserted = await queue.put_partial(ASRJob("session", "u1", 1, "partial", b"old", "en"))
    replaced = await queue.put_partial(ASRJob("session", "u1", 2, "partial", b"new", "en"))
    await queue.put_final(ASRJob("session", "u2", 1, "final", b"final", "en"))
    assert inserted is True
    assert replaced is False
    assert queue.depths == {"final": 1, "partial": 1}
    assert (await queue.get()).mode == "final"
    partial = await queue.get()
    assert partial.generation == 2
    assert partial.pcm == b"new"


def test_jobs_freeze_asr_and_correction_models() -> None:
    asr = ASRJob("s", "u", 1, "final", b"pcm", "zh-TW", "breeze-asr-25")
    text = TextJob("s", "u", "correction", "前句", "本句", "zh-TW", "disabled")

    assert asr.asr_model == "breeze-asr-25"
    assert text.correction_model == "disabled"


@pytest.mark.anyio
async def test_full_final_queue_raises_instead_of_dropping_audio() -> None:
    queue = ASRScheduler(max_finals=1, max_partials=1)
    await queue.put_final(ASRJob("s", "u1", 1, "final", b"one", "ja"))
    with pytest.raises(QueueFull):
        await queue.put_final(ASRJob("s", "u2", 1, "final", b"two", "ja"))


@pytest.mark.anyio
async def test_text_endpoint_precedes_correction_and_close_rejects_work() -> None:
    queue = TextScheduler(max_endpoints=1, max_corrections=1)
    correction = TextJob("s", "u1", "correction", "前句", "本句", "zh-TW")
    endpoint = TextJob("s", "u2", "endpoint", "", "因為", "zh-TW")
    await queue.put_correction(correction)
    await queue.put_endpoint(endpoint)
    assert queue.depths == {"endpoint": 1, "correction": 1}
    assert (await queue.get()).mode == "endpoint"
    assert (await queue.get()).mode == "correction"

    await queue.close()
    with pytest.raises(QueueClosed):
        await queue.put_endpoint(endpoint)
    with pytest.raises(QueueClosed):
        await queue.get()


@pytest.mark.anyio
async def test_distinct_full_partial_queue_is_bounded() -> None:
    queue = ASRScheduler(max_finals=1, max_partials=1)
    await queue.put_partial(ASRJob("s", "u1", 1, "partial", b"one", "ko"))
    with pytest.raises(QueueFull):
        await queue.put_partial(ASRJob("s", "u2", 1, "partial", b"two", "ko"))
