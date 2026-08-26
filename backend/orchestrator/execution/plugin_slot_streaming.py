"""SoAI - Plugin slot streaming iterator helpers [backend/orchestrator/execution/plugin_slot_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from typing import TYPE_CHECKING, Self

from core.concurrency.async_iterators import close_async_iterator_if_supported
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.task_groups import cancel_and_await
from orchestrator.execution.streaming import build_stream_timeout_error

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk

__all__ = (
    "prefetch_first_stream_item",
    "yield_prefetched_then_iterate",
)


async def prefetch_first_stream_item(
    result: AsyncIterable[StreamChunk],
    *,
    timeout: float,
) -> tuple[StreamChunk | None, AsyncIterator[StreamChunk]]:
    iterator = aiter(result)
    should_close_iterator = True

    try:
        timeout_scope = asyncio.timeout(timeout)
        try:
            async with timeout_scope:
                first_item = await anext(iterator)
        except TimeoutError as timeout_exc:
            raise build_stream_timeout_error(timeout_scope, timeout) from timeout_exc
        should_close_iterator = False
    except StopAsyncIteration:
        should_close_iterator = False
        return (None, iterator)
    finally:
        if should_close_iterator:
            await close_async_iterator_if_supported(iterator)
    return (first_item, iterator)


class PrefetchedStreamingIterator:
    _closed: bool
    _first_item: StreamChunk | None
    _iterator: AsyncIterator[StreamChunk]
    _next_lock: asyncio.Lock
    _pending_next_task: asyncio.Task[StreamChunk] | None
    _state_lock: asyncio.Lock

    def __init__(
        self,
        first_item: StreamChunk | None,
        iterator: AsyncIterator[StreamChunk],
    ) -> None:
        self._closed = False
        self._first_item = first_item
        self._iterator = iterator
        self._next_lock = asyncio.Lock()
        self._pending_next_task = None
        self._state_lock = asyncio.Lock()

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> StreamChunk:
        async with self._next_lock:
            async with self._state_lock:
                if self._closed:
                    raise StopAsyncIteration
                if self._first_item is not None:
                    first_item = self._first_item
                    self._first_item = None
                    return first_item
                next_task: asyncio.Task[StreamChunk] = asyncio.create_task(
                    _next_stream_item(self._iterator),
                    name="orchestrator.execution.plugin_slot_streaming.next_item",
                )
                self._pending_next_task = next_task
            try:
                return await next_task
            except StopAsyncIteration:
                await self.aclose()
                raise
            except asyncio.CancelledError:
                await uncancel_then_cleanup(
                    cancel_and_await((next_task,), task_label="prefetched stream next task"),
                )
                raise
            finally:
                await self._clear_pending_next_task(next_task)

    async def aclose(self) -> None:
        pending_next_task = await self._mark_closed()
        if pending_next_task is not None and not pending_next_task.done():
            await uncancel_then_cleanup(
                cancel_and_await((pending_next_task,), task_label="prefetched stream next task"),
            )
        await close_async_iterator_if_supported(self._iterator)

    async def _mark_closed(self) -> asyncio.Task[StreamChunk] | None:
        async with self._state_lock:
            if self._closed:
                return None
            self._closed = True
            self._first_item = None
            return self._pending_next_task

    async def _clear_pending_next_task(self, next_task: asyncio.Task[StreamChunk]) -> None:
        async with self._state_lock:
            if self._pending_next_task is next_task:
                self._pending_next_task = None


def yield_prefetched_then_iterate(
    first_item: StreamChunk | None,
    iterator: AsyncIterator[StreamChunk],
) -> AsyncIterator[StreamChunk]:
    return PrefetchedStreamingIterator(first_item, iterator)


async def _next_stream_item(iterator: AsyncIterator[StreamChunk]) -> StreamChunk:
    return await anext(iterator)
