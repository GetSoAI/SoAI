"""SoAI - Event bus worker loop [backend/core/events/bus_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeGuard

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.bus_dispatch import dispatch_callbacks
from core.events.bus_sentinel import EventBusSentinel
from core.events.bus_stuck_callback_registry import EventBusStuckCallbackRegistry
from core.events.completion_signals import (
    EventDispatchCompletion,
    mark_completion_signal_completed,
)
from core.events.protocols import EventCompletionSignal
from core.events.types_base import Event
from core.logging.protocols import TraceLogger
from core.metrics.keyspace_paths_event_streaming import (
    EVENT_BUS_GAUGE_QUEUE_DEPTH,
    EVENT_BUS_TIMING_QUEUE_TIME_MS,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.timing.monotonic import monotonic_ms
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

    type EventQueueItem = tuple[Event, int, EventCompletionSignal | None]

__all__ = (
    "is_event_queue_item",
    "run_event_bus_worker",
)

OPERATION = "event_bus.worker"


def is_event_queue_item(
    value: EventQueueItem | type[EventBusSentinel],
) -> TypeGuard[EventQueueItem]:
    if not isinstance(value, tuple) or len(value) != 3:
        return False
    event, publish_time, completion_event = value
    if not isinstance(event, Event):
        return False
    if not is_strict_int(publish_time):
        return False
    if completion_event is not None and (
        not isinstance(completion_event, asyncio.Event | EventDispatchCompletion)
    ):
        return False
    return True


async def run_event_bus_worker(
    *,
    worker_id: int,
    queue: asyncio.Queue[EventQueueItem | type[EventBusSentinel]],
    sentinel: type[EventBusSentinel],
    metrics_recorder: MetricsManagerProtocol | None,
    collect_callbacks: Callable[[Event], list[Callable[[Event], Awaitable[None]]]],
    dispatch_timeout: float | None,
    per_callback_timeout: float | None,
    logger: TraceLogger,
    stuck_callback_registry: EventBusStuckCallbackRegistry,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
) -> None:
    logger.trace("EventBus worker-%s started.", worker_id)
    while True:
        item = completion_event = None
        trace_id: str | None = None
        dispatch_timed_out = False
        dispatch_failure_message: str | None = None
        try:
            item = await queue.get()
            if item is sentinel:
                queue.task_done()
                break
            if not is_event_queue_item(item):
                raise TypeError(f"Event bus queue item is invalid: {type(item).__name__}")
            event, publish_time, completion_event = item
            trace_id = None
            if metrics_recorder:
                metrics_recorder.record_timing(
                    *EVENT_BUS_TIMING_QUEUE_TIME_MS,
                    duration_ms=float(monotonic_ms() - int(publish_time)),
                )
                metrics_recorder.set_gauge(*EVENT_BUS_GAUGE_QUEUE_DEPTH, value=queue.qsize())
            callbacks = collect_callbacks(event)
            if callbacks:
                dispatch_result = await dispatch_callbacks(
                    callbacks=callbacks,
                    event=event,
                    logger=logger,
                    metrics_recorder=metrics_recorder,
                    dispatch_timeout=dispatch_timeout,
                    per_callback_timeout=per_callback_timeout,
                    stuck_callback_registry=stuck_callback_registry,
                    finalizer_tracker=finalizer_tracker,
                    cancellation_binder=cancellation_binder,
                    cancellation_id=f"event-bus-worker:{worker_id}",
                )
                dispatch_timed_out = dispatch_result.aggregate_timed_out
                dispatch_failure_message = dispatch_result.failure_message
        except asyncio.CancelledError:
            break
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                trace_id=trace_id,
                operation="event_bus.worker",
            )
            try:
                coerced_trace_id = coerced.trace_id
            except AttributeError:
                coerced_trace_id = None
            log_exception(
                logger,
                coerced,
                message=f"Critical error in EventBus worker-{worker_id}",
                trace_id=coerced_trace_id,
                operation=OPERATION,
            )
            dispatch_failure_message = str(coerced)
        finally:
            mark_completion_signal_completed(
                completion_event,
                dispatch_timed_out=dispatch_timed_out,
                failure_message=dispatch_failure_message,
            )
            if item is not None and item is not sentinel:
                queue.task_done()
    logger.trace("EventBus worker-%s shutting down.", worker_id)
