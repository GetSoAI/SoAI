"""SoAI - Event bus callback execution helper [backend/core/events/bus_dispatch_callback_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.bus_callback_identity import describe_callback
from core.events.bus_dispatch_logging import resolve_event_trace_id
from core.events.bus_dispatch_waiting import wait_until_done
from core.events.bus_stuck_callback_registry import EventBusStuckCallbackRegistry
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_paths_event_streaming import (
    EVENT_BUS_COUNTER_CALLBACKS_REFUSED_CANCELLATION,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = ("execute_callback_with_timeout",)

EVENT_BUS_CALLBACK_CANCELLATION_WAIT_SEC: float = DEFAULT_CANCELLATION_TIMEOUT_SEC
OPERATION_EXECUTE_CALLBACK = "core.events.bus_dispatch_callback_execution"


async def _cancel_callback_task(
    *,
    callback_task: asyncio.Task[None],
    callback_name: str,
    callback: Callable[[Event], Awaitable[None]],
    event: Event,
    logger: LoggerProtocol,
    trace_id: str | None,
    stuck_callback_registry: EventBusStuckCallbackRegistry,
    metrics_recorder: MetricsManagerProtocol | None,
) -> Exception | None:
    callback_task.cancel()
    still_pending = await cancel_and_await(
        [callback_task],
        timeout_sec=EVENT_BUS_CALLBACK_CANCELLATION_WAIT_SEC,
    )
    if not still_pending:
        return None
    if metrics_recorder is not None:
        metrics_recorder.increment_counter(*EVENT_BUS_COUNTER_CALLBACKS_REFUSED_CANCELLATION)
    return stuck_callback_registry.quarantine_callback(
        task=callback_task,
        callback_id=callback_name,
        callback=callback,
        event=event,
        trace_id=trace_id,
        logger=logger,
    )


async def execute_callback_with_timeout(
    *,
    callback: Callable[[Event], Awaitable[None]],
    event: Event,
    per_callback_timeout: float | None,
    logger: LoggerProtocol,
    stuck_callback_registry: EventBusStuckCallbackRegistry,
    metrics_recorder: MetricsManagerProtocol | None,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    cancellation_id: str,
) -> Exception | None:
    callback_name = describe_callback(callback)
    trace_id = resolve_event_trace_id(event)

    async def run_callback() -> None:
        await callback(event)

    callback_task: asyncio.Task[None] = spawn_tracked_task(
        run_callback(),
        name=f"event-bus-callback:{callback_name}",
        logger=logger,
        finalizer_tracker=finalizer_tracker,
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id,
        owner="event-bus-callback",
        owner_observes_result=True,
    )
    try:
        if per_callback_timeout is None:
            await asyncio.shield(callback_task)
            return None
        finished = await wait_until_done(callback_task, per_callback_timeout)
        if finished:
            await callback_task
            return None
    except asyncio.CancelledError:
        logger.debug(
            "Callback %s cancelled for event %s",
            callback_name,
            type(event).__name__,
        )
        cancellation_error = await _cancel_callback_task(
            callback_task=callback_task,
            callback_name=callback_name,
            callback=callback,
            event=event,
            logger=logger,
            trace_id=trace_id,
            stuck_callback_registry=stuck_callback_registry,
            metrics_recorder=metrics_recorder,
        )
        if cancellation_error is not None:
            return cancellation_error
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_EXECUTE_CALLBACK,
        )
        log_exception(
            logger,
            coerced,
            message=f"Callback {callback_name} raised exception",
            operation=OPERATION_EXECUTE_CALLBACK,
        )
        return coerced
    logger.warning(
        "Callback %s timed out after %.3fs for event %s",
        callback_name,
        per_callback_timeout,
        type(event).__name__,
    )
    cancellation_error = await _cancel_callback_task(
        callback_task=callback_task,
        callback_name=callback_name,
        callback=callback,
        event=event,
        logger=logger,
        trace_id=trace_id,
        stuck_callback_registry=stuck_callback_registry,
        metrics_recorder=metrics_recorder,
    )
    if cancellation_error is not None:
        return cancellation_error
    return TimeoutError(f"Callback {callback_name} exceeded {per_callback_timeout:.3f}s")
