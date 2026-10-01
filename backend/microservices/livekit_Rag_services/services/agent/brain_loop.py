"""
One long-lived event loop for Vocira's own work: database, Redis,
RabbitMQ, the school's records and knowledge.

The framework runs every call on an event loop of its own (on Windows, a
thread with a new loop per call). Vocira's async clients - the
database pool, the Redis client, the RabbitMQ connection, its locks -
are made once per process and tie themselves to the loop they were
first used on, so a second call on another loop broke them ("attached
to a different loop"). Running all of that on this one loop, as the
older worker always did, keeps them working; a call only hands its
question over and waits for the answer.
"""

import asyncio
import threading
from collections.abc import AsyncIterator, Awaitable
from typing import TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_lock = threading.Lock()


def brain_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _lock:
        if _loop is None:
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, name="vocira-brain", daemon=True).start()
            _loop = loop
    return _loop


async def on_brain(work: Awaitable[T]) -> T:
    """Run a coroutine on the brain loop and wait for it from the call's own loop."""
    future = asyncio.run_coroutine_threadsafe(work, brain_loop())
    try:
        return await asyncio.wrap_future(future)
    except asyncio.CancelledError:
        # the call stopped waiting (the caller interrupted or left)
        future.cancel()
        raise


def fire_on_brain(work: Awaitable) -> None:
    """Start a coroutine on the brain loop and not wait - it outlives the call's own task."""

    def report(future) -> None:
        if not future.cancelled() and future.exception() is not None:
            print(f"[Brain] background work failed: {future.exception()!r}")

    asyncio.run_coroutine_threadsafe(work, brain_loop()).add_done_callback(report)


async def stream_from_brain(source: AsyncIterator[T]) -> AsyncIterator[T]:
    """Pass the items of an async iterator made on the brain loop to the call's own loop as they come."""
    here = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    done = object()

    async def pump() -> None:
        try:
            async for item in source:
                here.call_soon_threadsafe(queue.put_nowait, (item, None))
        except Exception as error:  # handed over, raised on the call's side
            here.call_soon_threadsafe(queue.put_nowait, (done, error))
            return
        here.call_soon_threadsafe(queue.put_nowait, (done, None))

    future = asyncio.run_coroutine_threadsafe(pump(), brain_loop())
    try:
        while True:
            item, error = await queue.get()
            if item is done:
                if error is not None:
                    raise error
                return
            yield item
    finally:
        future.cancel()
