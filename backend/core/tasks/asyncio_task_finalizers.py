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
    is_coroutine,
    try_close_unawaited,
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
    attachment_ready = asyncio.Event()

    async def _await_attached() -> TaskResult:
        await attachment_ready.wait()
        return await awaitable_value

    gated = _await_attached()
    task: asyncio.Task[TaskResult] | None = None
    attached = False
    try:
        task = create_task_with_rejection_cleanup(
            gated,
            loop=loop,
            name=name,
            rejection_cleanup=(gated, *rejection_cleanup),
        )
        attach_tracked_task_lifecycle(
            task,
            logger=logger,
            done_callback=done_callback,
            awaitable_value=callback_awaitable,
            finalizer_tracker=finalizer_tracker,
            owner_observes_result=owner_observes_result,
        )
        if is_coroutine(awaitable_value):
            task.add_done_callback(
                partial(close_awaitable_if_cancelled, awaitable_value=awaitable_value),
            )
        attachment_ready.set()
        attached = True
        return task
    finally:
        if not attached:
            if task is not None:
                task.cancel()
            else:
                try_close_unawaited(gated)
            if is_coroutine(awaitable_value):
                try_close_unawaited(awaitable_value)
            for coroutine in rejection_cleanup:
                try_close_unawaited(coroutine)
            if callback_awaitable is not None:
                try_close_unawaited(callback_awaitable)


def attach_tracked_task_lifecycle[TaskResult](
    task: asyncio.Task[TaskResult],
    *,
    logger: LoggerProtocol | None,
    done_callback: Callable[[asyncio.Task[TaskResult]], None] | None = None,
    awaitable_value: Coroutine[None, None, TaskResult] | None = None,
    finalizer_tracker: TaskFinalizerTrackerProtocol | None = None,
    owner_observes_result: bool = False,
) -> None:
    tracking_ready = asyncio.Event()

    async def _await_original_task() -> None:
        await tracking_ready.wait()
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

    tracking_coroutine: Coroutine[None, None, None] | None = None
    finalizer_task: asyncio.Task[None] | None = None
    attached = False
    try:
        if finalizer_tracker is not None:
            tracking_coroutine = _await_original_task()
            finalizer_task = asyncio.create_task(
                tracking_coroutine,
                name=f"finalizer:{task.get_name()}",
            )
            finalizer_tracker.track_finalizer(finalizer_task)
        if awaitable_value is not None:
            task.add_done_callback(
                partial(close_awaitable_if_cancelled, awaitable_value=awaitable_value),
            )
        if logger is not None and not owner_observes_result:
            task.add_done_callback(partial(log_task_exception, logger=logger))
        if done_callback is not None:
            task.add_done_callback(done_callback)
        tracking_ready.set()
        attached = True
    finally:
        if not attached:
            if finalizer_task is not None:
                finalizer_task.cancel()
            elif tracking_coroutine is not None:
                try_close_unawaited(tracking_coroutine)
