"""SoAI - Plugin slot streaming iterator helpers [backend/orchestrator/execution/plugin_slot_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Callable
from typing import TYPE_CHECKING, Self

from core.concurrency.async_iterators import (
    close_async_iterator_if_supported,
    settle_async_iterator_read_then_close,
)
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import SoAITimeoutError
from core.tasks.protocols import TaskFinalizerTrackerProtocol, TaskRegistryProtocol
from core.tasks.task import Task
from orchestrator.execution.execution_phase_timeouts import await_execution_phase
from orchestrator.execution.streaming import StreamingIdleTimeoutError, StreamingSourceTimeoutError

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
    task_registry: TaskRegistryProtocol | None = None,
    task: Task | None = None,
    timeout_error: Callable[[], SoAITimeoutError] | None = None,
) -> tuple[StreamChunk | None, AsyncIterator[StreamChunk]]:
    iterator = aiter(result)
    should_close_iterator = True
    try:
        try:
            first_item = await await_execution_phase(
                anext(iterator),
                timeout_seconds=timeout,
                timeout_error=timeout_error or (lambda: StreamingIdleTimeoutError(timeout)),
                task_registry=task_registry,
                task=task,
            )
        except TimeoutError as exception:
            raise StreamingSourceTimeoutError(timeout) from exception
        except StopAsyncIteration:
            should_close_iterator = False
            return (None, iterator)
        should_close_iterator = False
    finally:
        if should_close_iterator:
            await close_async_iterator_if_supported(iterator)
    return (first_item, iterator)


class PrefetchedStreamingIterator:
    _closed: bool
    _close_task: asyncio.Task[None] | None
    _close_task_tracked: bool
    _finalizer_tracker: TaskFinalizerTrackerProtocol
    _first_item: StreamChunk | None
    _iterator: AsyncIterator[StreamChunk]
    _next_lock: asyncio.Lock
    _pending_next_task: asyncio.Task[StreamChunk] | None
    _state_lock: asyncio.Lock

    def __init__(
        self,
        first_item: StreamChunk | None,
        iterator: AsyncIterator[StreamChunk],
        *,
        finalizer_tracker: TaskFinalizerTrackerProtocol,
    ) -> None:
        self._closed = False
        self._close_task = None
        self._close_task_tracked = False
        self._finalizer_tracker = finalizer_tracker
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
                return await asyncio.shield(next_task)
            except StopAsyncIteration:
                await self.aclose()
                raise
            except asyncio.CancelledError:
                await self.aclose()
                raise
            finally:
                await self._clear_pending_next_task(next_task)

    async def aclose(self) -> None:
        async with self._state_lock:
            if self._close_task is None:
                self._closed = True
                self._first_item = None
                self._close_task = create_ephemeral_task(
                    settle_async_iterator_read_then_close(self._iterator, self._pending_next_task),
                    name="orchestrator.execution.plugin_slot_streaming.close",
                    log_exceptions=False,
                )
            close_task = self._close_task
        try:
            await uncancel_then_cleanup(close_task)
        finally:
            if not close_task.done() and not self._close_task_tracked:
                self._close_task_tracked = True
                self._finalizer_tracker.track_finalizer(close_task)

    async def _clear_pending_next_task(self, next_task: asyncio.Task[StreamChunk]) -> None:
        async with self._state_lock:
            if self._pending_next_task is next_task:
                self._pending_next_task = None


def yield_prefetched_then_iterate(
    first_item: StreamChunk | None,
    iterator: AsyncIterator[StreamChunk],
    *,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> AsyncIterator[StreamChunk]:
    return PrefetchedStreamingIterator(first_item, iterator, finalizer_tracker=finalizer_tracker)


async def _next_stream_item(iterator: AsyncIterator[StreamChunk]) -> StreamChunk:
    return await anext(iterator)
