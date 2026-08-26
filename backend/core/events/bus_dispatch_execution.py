"""SoAI - Event bus callback dispatch execution helpers [backend/core/events/bus_dispatch_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.task_groups import DEFAULT_CANCELLATION_TIMEOUT_SEC
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.bus_callback_identity import describe_callback
from core.events.bus_dispatch_callback_execution import execute_callback_with_timeout
from core.events.bus_dispatch_waiting import (
    await_cancelled_callback_tasks,
    wait_until_done,
)
from core.events.bus_stuck_callback_registry import EventBusStuckCallbackRegistry
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = (
    "dispatch_multiple_callbacks",
    "dispatch_single_callback",
)

OPERATION = "event_bus.dispatch.callback"


def _resolve_cancellation_wait_timeout(dispatch_timeout: float) -> float:
    return max(float(dispatch_timeout), DEFAULT_CANCELLATION_TIMEOUT_SEC)


async def dispatch_single_callback(
    *,
    callback: Callable[[Event], Awaitable[None]],
    event: Event,
    logger: LoggerProtocol,
    dispatch_timeout: float | None,
    per_callback_timeout: float | None,
    trace_id: str | None,
    stuck_callback_registry: EventBusStuckCallbackRegistry,
    metrics_recorder: MetricsManagerProtocol | None,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    cancellation_id: str,
) -> tuple[bool, BaseException | None]:
    callback_name = describe_callback(callback)
    task = spawn_tracked_task(
        execute_callback_with_timeout(
            callback=callback,
            event=event,
            per_callback_timeout=per_callback_timeout,
            logger=logger,
            stuck_callback_registry=stuck_callback_registry,
            metrics_recorder=metrics_recorder,
            finalizer_tracker=finalizer_tracker,
            cancellation_binder=cancellation_binder,
            cancellation_id=cancellation_id,
        ),
        name=f"event-bus-dispatch:{type(event).__name__}:{callback_name}",
        logger=logger,
        finalizer_tracker=finalizer_tracker,
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id,
        owner="event-bus-dispatch",
        owner_observes_result=True,
    )
    if dispatch_timeout is None:
        try:
            result = await task
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                trace_id=trace_id,
                operation=OPERATION,
            )
            log_exception(
                logger,
                coerced,
                message="Unhandled exception while dispatching event bus callback.",
                trace_id=trace_id,
                operation=OPERATION,
                details={
                    "callback": callback_name,
                    "event_type": type(event).__name__,
                },
            )
            return False, exception
        return False, result
    try:
        finished = await wait_until_done(task, dispatch_timeout)
        if not finished:
            logger.warning(
                "Aggregate dispatch timed out after %.3fs for %s.",
                dispatch_timeout,
                type(event).__name__,
            )
            task.cancel()
            await await_cancelled_callback_tasks(
                tasks=[task],
                callbacks=[callback],
                event=event,
                logger=logger,
                cancellation_wait_timeout=_resolve_cancellation_wait_timeout(dispatch_timeout),
            )
            return True, None
        result = task.result()
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            trace_id=trace_id,
            operation=OPERATION,
        )
        log_exception(
            logger,
            coerced,
            message="Unhandled exception while dispatching event bus callback.",
            trace_id=trace_id,
            operation=OPERATION,
            details={
                "callback": callback_name,
                "event_type": type(event).__name__,
            },
        )
        return False, exception
    return False, result


async def dispatch_multiple_callbacks(
    *,
    callbacks: list[Callable[[Event], Awaitable[None]]],
    event: Event,
    logger: LoggerProtocol,
    dispatch_timeout: float | None,
    per_callback_timeout: float | None,
    stuck_callback_registry: EventBusStuckCallbackRegistry,
    metrics_recorder: MetricsManagerProtocol | None,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    cancellation_id: str,
) -> tuple[
    bool,
    dict[asyncio.Task[Exception | None], BaseException | None],
    list[asyncio.Task[Exception | None]],
]:
    tasks = [
        spawn_tracked_task(
            execute_callback_with_timeout(
                callback=callback,
                event=event,
                per_callback_timeout=per_callback_timeout,
                logger=logger,
                stuck_callback_registry=stuck_callback_registry,
                metrics_recorder=metrics_recorder,
                finalizer_tracker=finalizer_tracker,
                cancellation_binder=cancellation_binder,
                cancellation_id=f"{cancellation_id}:{index}",
            ),
            name=f"event-bus-dispatch:{type(event).__name__}:{index}",
            logger=logger,
            finalizer_tracker=finalizer_tracker,
            cancellation_binder=cancellation_binder,
            cancellation_id=f"{cancellation_id}:{index}",
            owner="event-bus-dispatch",
            owner_observes_result=True,
        )
        for index, callback in enumerate(callbacks)
    ]
    results_by_task: dict[asyncio.Task[Exception | None], BaseException | None] = {}
    if dispatch_timeout is None:
        gathered_results = list(await asyncio.gather(*tasks, return_exceptions=True))
        for task, result in zip(tasks, gathered_results, strict=True):
            results_by_task[task] = result
        return False, results_by_task, tasks
    completed_tasks, pending_tasks = await asyncio.wait(tasks, timeout=dispatch_timeout)
    for completed_task in completed_tasks:
        completed_result: BaseException | None
        try:
            completed_result = completed_task.result()
        except asyncio.CancelledError as exception:
            completed_result = exception
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION)
            log_exception(
                logger,
                coerced,
                message="Unhandled exception while collecting event bus callback result.",
                operation=OPERATION,
                details={
                    "task_name": completed_task.get_name(),
                    "event_type": type(event).__name__,
                },
            )
            completed_result = exception
        results_by_task[completed_task] = completed_result
    if not pending_tasks:
        return False, results_by_task, tasks
    logger.warning(
        "Aggregate dispatch timed out after %.3fs for %s. Cancelling %s callback task(s).",
        dispatch_timeout,
        type(event).__name__,
        len(pending_tasks),
    )
    pending_pairs = [
        (callback, task)
        for callback, task in zip(callbacks, tasks, strict=True)
        if task in pending_tasks
    ]
    pending_callbacks = [pair[0] for pair in pending_pairs]
    pending_tasks_list = [pair[1] for pair in pending_pairs]
    for pending_task in pending_tasks_list:
        pending_task.cancel()
    await await_cancelled_callback_tasks(
        tasks=pending_tasks_list,
        callbacks=pending_callbacks,
        event=event,
        logger=logger,
        cancellation_wait_timeout=_resolve_cancellation_wait_timeout(dispatch_timeout),
    )
    return True, results_by_task, tasks
