"""Run awaitables concurrently with cancellation support."""

from __future__ import annotations

from asyncio import AbstractEventLoop, Task, gather, get_running_loop
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable

__all__ = ["gather_with_cancel"]

# Module-level cache for the running loop
_cached_loop: AbstractEventLoop | None = None


async def gather_with_cancel(*awaitables: Awaitable[Any]) -> list[Any]:
    """Run awaitable objects in the sequence concurrently.

    The first raised exception is immediately propagated to the task that awaits
    on this function and all pending awaitables in the sequence will be cancelled.
    """
    global _cached_loop  # noqa: PLW0603

    # Cache the running loop to avoid repeated get_running_loop() calls
    loop = _cached_loop
    if loop is None or not loop.is_running():
        loop = _cached_loop = get_running_loop()

    # Use loop.create_task directly - faster than asyncio.create_task
    tasks: list[Task[Any]] = [loop.create_task(aw) for aw in awaitables]  # type: ignore[arg-type]

    try:
        return await gather(*tasks)
    except Exception:
        for task in tasks:
            if not task.done():
                task.cancel()
        await gather(*tasks, return_exceptions=True)
        raise
