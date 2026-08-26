"""SoAI - Canonical tracked task spawner with bind-before-work cancellation support [backend/core/tasks/asyncio_task_spawner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, TypeGuard

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.tasks.asyncio_task_finalizers import create_tracked_task_lifecycle
from core.tasks.asyncio_task_tracking import (
    cancel_and_await_tracked_task,
    track_task_or_cancel,
)
from core.tasks.awaitable_cleanup import (
    await_wrapper,
    token_is_cancelled,
    try_close_unawaited,
)
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "create_tracked_and_track_task",
    "create_tracked_task",
    "spawn_tracked_task",
)

LOGGER_NAME = "SoAI.core.tasks.asyncio_task_spawner"
OPERATION_CORE_TASKS_ASYNCIO_TASK_SPAWNER_SPAWN_TRACKED_TASK = (
    "core.tasks.asyncio_task_spawner.spawn_tracked_task"
)


def _require_cancellation_binding(cancellation_id: str | None, owner: str) -> tuple[str, str]:
    cancellation_id_value = normalize_cancellation_id(cancellation_id)
    if not cancellation_id_value:
        raise ValidationError("cancellation_id is required when using a cancellation registry.")
    owner_value = str(owner or "").strip()
    if not owner_value:
        raise ValidationError("owner is required when using a cancellation registry.")
    return cancellation_id_value, owner_value


def _is_coroutine[TaskResult](
    value: Coroutine[None, None, TaskResult] | Awaitable[TaskResult],
) -> TypeGuard[Coroutine[None, None, TaskResult]]:
    return isinstance(value, Coroutine)


def spawn_tracked_task[TaskResult](
    coro: Coroutine[None, None, TaskResult] | Awaitable[TaskResult],
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    name: str | None = None,
    logger: LoggerProtocol | None = None,
    done_callback: Callable[[asyncio.Task[TaskResult]], None] | None = None,
    cancellation_binder: TaskCancellationBinderProtocol | None = None,
    cancellation_id: str | None = None,
    owner: str = "",
    metadata: dict[str, JSONValue] | None = None,
    finalizer_tracker: TaskFinalizerTrackerProtocol | None = None,
    owner_observes_result: bool = False,
) -> asyncio.Task[TaskResult]:
    awaitable_value: Awaitable[TaskResult] = coro
    closable_coroutine = coro if _is_coroutine(coro) else None
    if loop is not None and loop.is_closed():
        if closable_coroutine is not None:
            try_close_unawaited(closable_coroutine)
        raise ValidationError("Cannot spawn a task on a closed event loop.")

    if cancellation_binder is None:
        rejection_cleanup = (closable_coroutine,) if closable_coroutine is not None else ()
        task = create_tracked_task_lifecycle(
            awaitable_value,
            loop=loop,
            name=name,
            rejection_cleanup=rejection_cleanup,
            logger=logger,
            done_callback=done_callback,
            callback_awaitable=closable_coroutine,
            finalizer_tracker=finalizer_tracker,
            owner_observes_result=owner_observes_result,
        )
        return task
    cancellation_id_value, owner_value = _require_cancellation_binding(cancellation_id, owner)
    binding_ready = asyncio.Event()

    async def _gated() -> TaskResult:
        try:
            await binding_ready.wait()
            return await await_wrapper(awaitable_value)
        except asyncio.CancelledError:
            if closable_coroutine is not None:
                try_close_unawaited(closable_coroutine)
            raise

    gated_coroutine = _gated()
    rejection_cleanup = (closable_coroutine,) if closable_coroutine is not None else ()
    task = create_tracked_task_lifecycle(
        gated_coroutine,
        loop=loop,
        name=name,
        rejection_cleanup=(gated_coroutine, *rejection_cleanup),
        logger=logger,
        done_callback=done_callback,
        callback_awaitable=closable_coroutine,
        finalizer_tracker=finalizer_tracker,
        owner_observes_result=owner_observes_result,
    )

    async def _bind_task() -> None:
        task_logger = get_logger(LOGGER_NAME)
        try:
            token = await cancellation_binder.bind_task(
                cancellation_id_value,
                task,
                owner=owner_value,
                metadata=metadata,
            )
            if await token_is_cancelled(token) and (not task.done()):
                task.cancel()
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                task_logger,
                exception,
                message="Failed to bind task to cancellation registry. Cancelling task.",
                operation=OPERATION_CORE_TASKS_ASYNCIO_TASK_SPAWNER_SPAWN_TRACKED_TASK,
                details={"cancellation_id": cancellation_id_value, "owner": owner_value},
                level="warning",
            )
            if not task.done():
                task.cancel()
        finally:
            binding_ready.set()

    binder_name = f"bind-task-{cancellation_id_value}"
    bind_task: asyncio.Task[None]
    bind_task_created = False
    try:
        bind_task = create_ephemeral_task(
            _bind_task(),
            name=binder_name,
            log_exceptions=finalizer_tracker is None,
        )
        bind_task_created = True
    finally:
        if not bind_task_created:
            binding_ready.set()
            task.cancel()
    if finalizer_tracker is not None:
        finalizer_tracker.track_finalizer(bind_task)
    return task


async def create_tracked_task[TaskResult](
    coro: Coroutine[None, None, TaskResult] | Awaitable[TaskResult],
    *,
    cancellation_binder: TaskCancellationBinderProtocol,
    cancellation_id: str,
    owner: str,
    name: str | None = None,
    logger: LoggerProtocol | None = None,
    done_callback: Callable[[asyncio.Task[TaskResult]], None] | None = None,
    metadata: dict[str, JSONValue] | None = None,
) -> asyncio.Task[TaskResult]:
    cancellation_id_value, owner_value = _require_cancellation_binding(cancellation_id, owner)
    awaitable_value: Awaitable[TaskResult] = coro
    closable_coroutine = coro if _is_coroutine(coro) else None
    binding_ready = asyncio.Event()

    async def _gated() -> TaskResult:
        try:
            await binding_ready.wait()
            return await await_wrapper(awaitable_value)
        except asyncio.CancelledError:
            if closable_coroutine is not None:
                try_close_unawaited(closable_coroutine)
            raise

    gated_coroutine = _gated()
    rejection_cleanup = (closable_coroutine,) if closable_coroutine is not None else ()
    task = create_tracked_task_lifecycle(
        gated_coroutine,
        name=name,
        rejection_cleanup=(gated_coroutine, *rejection_cleanup),
        logger=logger,
        done_callback=done_callback,
        callback_awaitable=closable_coroutine,
    )
    try:
        token = await cancellation_binder.bind_task(
            cancellation_id_value,
            task,
            owner=owner_value,
            metadata=metadata,
        )
        if await token_is_cancelled(token) and (not task.done()):
            task.cancel()
    except asyncio.CancelledError:
        await cancel_and_await_tracked_task(task, logger=logger)
        raise
    except RECOVERABLE_EXCEPTIONS:
        await cancel_and_await_tracked_task(task, logger=logger)
        raise
    finally:
        binding_ready.set()
    return task


async def create_tracked_and_track_task[TaskResult](
    coro: Coroutine[None, None, TaskResult] | Awaitable[TaskResult],
    *,
    cancellation_binder: TaskCancellationBinderProtocol,
    cancellation_id: str,
    owner: str,
    track_task: Callable[[asyncio.Task[TaskResult]], None],
    name: str | None = None,
    logger: LoggerProtocol | None = None,
    done_callback: Callable[[asyncio.Task[TaskResult]], None] | None = None,
    metadata: dict[str, JSONValue] | None = None,
) -> asyncio.Task[TaskResult]:
    task = await create_tracked_task(
        coro,
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id,
        owner=owner,
        name=name,
        logger=logger,
        done_callback=done_callback,
        metadata=metadata,
    )
    try:
        await track_task_or_cancel(
            task,
            track_task=track_task,
            logger=logger,
            cancellation_id=cancellation_id,
            owner=owner,
        )
    except asyncio.CancelledError:
        await cancel_and_await_tracked_task(task, logger=logger)
        raise
    return task
