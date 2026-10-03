"""SoAI - Tracked task finalizer helpers [backend/core/tasks/asyncio_task_finalizers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from functools import partial

from core.logging.protocols import LoggerProtocol
from core.tasks.awaitable_cleanup import (
    close_awaitable_if_cancelled,
    create_task_with_rejection_cleanup,
)
from core.tasks.logging import log_task_exception
from core.tasks.protocols import TaskFinalizerTrackerProtocol

__all__ = (
    "attach_tracked_task_lifecycle",
    "create_tracked_task_lifecycle",
)


def create_tracked_task_lifecycle[TaskResult](
    awaitable_value: Awaitable[TaskResult],
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    name: str | None = None,
    rejection_cleanup: tuple[Coroutine[None, None, TaskResult], ...] = (),
    logger: LoggerProtocol | None,
    done_callback: Callable[[asyncio.Task[TaskResult]], None] | None = None,
    callback_awaitable: Coroutine[None, None, TaskResult] | None = None,
    finalizer_tracker: TaskFinalizerTrackerProtocol | None = None,
    owner_observes_result: bool = False,
) -> asyncio.Task[TaskResult]:
    task = create_task_with_rejection_cleanup(
        awaitable_value,
        loop=loop,
        name=name,
        rejection_cleanup=rejection_cleanup,
    )
    attach_tracked_task_lifecycle(
        task,
        logger=logger,
        done_callback=done_callback,
        awaitable_value=callback_awaitable,
        finalizer_tracker=finalizer_tracker,
        owner_observes_result=owner_observes_result,
    )
    return task


def attach_tracked_task_lifecycle[TaskResult](
    task: asyncio.Task[TaskResult],
    *,
    logger: LoggerProtocol | None,
    done_callback: Callable[[asyncio.Task[TaskResult]], None] | None = None,
    awaitable_value: Coroutine[None, None, TaskResult] | None = None,
    finalizer_tracker: TaskFinalizerTrackerProtocol | None = None,
    owner_observes_result: bool = False,
) -> None:
    if awaitable_value is not None:
        task.add_done_callback(
            partial(close_awaitable_if_cancelled, awaitable_value=awaitable_value),
        )
    if logger is not None and not owner_observes_result:
        task.add_done_callback(partial(log_task_exception, logger=logger))
    if done_callback is not None:
        task.add_done_callback(done_callback)
    if finalizer_tracker is None:
        return
    create_task = asyncio.create_task

    async def _await_original_task() -> None:
        outcomes = await asyncio.gather(task, return_exceptions=True)
        exception = outcomes[0]
        if isinstance(exception, asyncio.CancelledError):
            if owner_observes_result:
                return
            raise exception
        if not isinstance(exception, BaseException):
            return
        if owner_observes_result or logger is not None:
            return
        raise exception

    finalizer_task = create_task(
        _await_original_task(),
        name=f"finalizer:{task.get_name()}",
    )
    finalizer_tracker.track_finalizer(finalizer_task)
