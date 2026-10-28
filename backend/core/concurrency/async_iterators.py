"""SoAI - Async iterator lifecycle helpers [backend/core/concurrency/async_iterators.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from core.concurrency.cancellation_cleanup import (
    uncancel_then_cleanup,
    wait_for_task_completion,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.protocols import AsyncClosableIteratorProtocol
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from core.tasks.protocols import TaskFinalizerTrackerProtocol

__all__ = (
    "close_async_iterator_if_supported",
    "close_async_iterator_after_read",
    "settle_async_iterator_read_then_close",
)

LOGGER_NAME = "SoAI.core.concurrency.async_iterators"
OPERATION_SETTLE_READ = "core.concurrency.async_iterators.settle_read"


async def close_async_iterator_if_supported[Item](iterator: AsyncIterator[Item]) -> None:
    if isinstance(iterator, AsyncClosableIteratorProtocol):
        await uncancel_then_cleanup(iterator.aclose())


async def settle_async_iterator_read_then_close[Item](
    iterator: AsyncIterator[Item],
    read_task: asyncio.Task[Item] | None,
) -> None:
    if read_task is not None:
        if not read_task.done():
            read_task.cancel()
        await wait_for_task_completion(read_task, retain_resources_until_complete=True)
        if not read_task.cancelled():
            exception = read_task.exception()
            if exception is not None and not isinstance(exception, StopAsyncIteration):
                log_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Stream read failed during iterator cleanup.",
                    operation=OPERATION_SETTLE_READ,
                    details={"task_name": read_task.get_name()},
                )
    if isinstance(iterator, AsyncClosableIteratorProtocol):
        close_task = create_ephemeral_task(
            iterator.aclose(),
            name="core.concurrency.async_iterators.close",
            log_exceptions=False,
        )
        await wait_for_task_completion(close_task, retain_resources_until_complete=True)
        close_task.result()


async def close_async_iterator_after_read[Item](
    iterator: AsyncIterator[Item],
    read_task: asyncio.Task[Item] | None,
    *,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> None:
    close_task = create_ephemeral_task(
        settle_async_iterator_read_then_close(iterator, read_task),
        name="core.concurrency.async_iterators.close_after_read",
        log_exceptions=False,
    )
    try:
        await uncancel_then_cleanup(close_task)
    finally:
        if not close_task.done():
            finalizer_tracker.track_finalizer(close_task)
