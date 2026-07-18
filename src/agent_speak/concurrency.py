"""Bounded async boundary for synchronous provider and persistence operations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import ParamSpec, TypeVar


P = ParamSpec("P")
T = TypeVar("T")

_WORKERS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-speak")


async def run_sync(operation: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """Run blocking synchronous work away from the asyncio event-loop thread."""

    call = partial(operation, *args, **kwargs)
    future = _WORKERS.submit(call)
    while not future.done():
        await asyncio.sleep(0.001)
    return future.result()
