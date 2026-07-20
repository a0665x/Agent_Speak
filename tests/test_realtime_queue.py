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
    await queue.put_partial(ASRJob("session", "u1", 1, "partial", b"old"))
    await queue.put_partial(ASRJob("session", "u1", 2, "partial", b"new"))
    await queue.put_final(ASRJob("session", "u2", 1, "final", b"final"))
    assert queue.depths == {"final": 1, "partial": 1}
    assert (await queue.get()).mode == "final"
    partial = await queue.get()
    assert partial.generation == 2
    assert partial.pcm == b"new"


@pytest.mark.anyio
async def test_full_final_queue_raises_instead_of_dropping_audio() -> None:
    queue = ASRScheduler(max_finals=1, max_partials=1)
    await queue.put_final(ASRJob("s", "u1", 1, "final", b"one"))
    with pytest.raises(QueueFull):
        await queue.put_final(ASRJob("s", "u2", 1, "final", b"two"))


@pytest.mark.anyio
async def test_text_endpoint_precedes_correction_and_close_rejects_work() -> None:
    queue = TextScheduler(max_endpoints=1, max_corrections=1)
    correction = TextJob("s", "u1", "correction", "前句", "本句")
    endpoint = TextJob("s", "u2", "endpoint", "", "因為")
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
    await queue.put_partial(ASRJob("s", "u1", 1, "partial", b"one"))
    with pytest.raises(QueueFull):
        await queue.put_partial(ASRJob("s", "u2", 1, "partial", b"two"))
