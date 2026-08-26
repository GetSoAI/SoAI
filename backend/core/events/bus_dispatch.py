"""SoAI - Event bus callback dispatcher with timeout [backend/core/events/bus_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.bus_callback_identity import describe_callback
from core.events.bus_dispatch_execution import (
    dispatch_multiple_callbacks,
    dispatch_single_callback,
)
from core.events.bus_dispatch_logging import (
    log_dispatch_callback_exception,
    resolve_event_trace_id,
)
from core.events.bus_stuck_callback_registry import EventBusStuckCallbackRegistry
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_paths_event_streaming import (
    EVENT_BUS_GAUGE_DISPATCHED_CALLBACK_COUNT,
    EVENT_BUS_TIMING_DISPATCH_TIME_MS,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = (
    "DispatchCallbacksResult",
    "dispatch_callbacks",
)


@dataclass(frozen=True, slots=True)
class DispatchCallbacksResult:
    aggregate_timed_out: bool
    failure_message: str | None


def _build_quarantined_callback_failure_message(event: Event, skipped_callback_count: int) -> str:
    return (
        f"{skipped_callback_count} quarantined subscriber(s) were skipped for "
        f"{type(event).__name__}."
    )


def _record_dispatch_metrics(
    *,
    metrics_recorder: MetricsManagerProtocol | None,
    dispatch_duration_ms: int,
    callback_count: int,
) -> None:
    if metrics_recorder is None:
        return
    metrics_recorder.record_timing(
        *EVENT_BUS_TIMING_DISPATCH_TIME_MS,
        duration_ms=float(dispatch_duration_ms),
    )
    metrics_recorder.set_gauge(*EVENT_BUS_GAUGE_DISPATCHED_CALLBACK_COUNT, value=callback_count)


def _log_callback_result_exception(
    *,
    callback_result: BaseException | None,
    callback: Callable[[Event], Awaitable[None]],
    event: Event,
    logger: LoggerProtocol,
    trace_id: str | None,
) -> None:
    if callback_result is None:
        return
    if isinstance(callback_result, asyncio.TimeoutError):
        return
    if isinstance(callback_result, asyncio.CancelledError):
        return
    if isinstance(callback_result, Exception):
        log_dispatch_callback_exception(
            logger=logger,
            exception=callback_result,
            callback=callback,
            event=event,
            message=f"Unhandled exception in subscriber {describe_callback(callback)} for event {type(event).__name__}",
            trace_id=trace_id,
        )


async def dispatch_callbacks(
    *,
    callbacks: list[Callable[[Event], Awaitable[None]]],
    event: Event,
    logger: LoggerProtocol,
    metrics_recorder: MetricsManagerProtocol | None,
    dispatch_timeout: float | None,
    per_callback_timeout: float | None,
    stuck_callback_registry: EventBusStuckCallbackRegistry,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    cancellation_id: str,
) -> DispatchCallbacksResult:
    dispatch_start_ms = monotonic_ms()
    dispatchable_callbacks = [
        callback for callback in callbacks if not stuck_callback_registry.is_quarantined(callback)
    ]
    skipped_callback_count = len(callbacks) - len(dispatchable_callbacks)
    quarantine_failure_message: str | None = None
    if skipped_callback_count:
        logger.warning(
            "Event bus skipped %d quarantined callback(s) for %s.",
            skipped_callback_count,
            type(event).__name__,
        )
        quarantine_failure_message = _build_quarantined_callback_failure_message(
            event,
            skipped_callback_count,
        )
    callback_count = len(dispatchable_callbacks)
    if callback_count == 0:
        return DispatchCallbacksResult(
            aggregate_timed_out=False,
            failure_message=quarantine_failure_message,
        )
    trace_id = resolve_event_trace_id(event)
    if callback_count == 1:
        callback = dispatchable_callbacks[0]
        aggregate_timed_out, result = await dispatch_single_callback(
            callback=callback,
            event=event,
            logger=logger,
            dispatch_timeout=dispatch_timeout,
            per_callback_timeout=per_callback_timeout,
            trace_id=trace_id,
            stuck_callback_registry=stuck_callback_registry,
            metrics_recorder=metrics_recorder,
            finalizer_tracker=finalizer_tracker,
            cancellation_binder=cancellation_binder,
            cancellation_id=cancellation_id,
        )
        dispatch_duration_ms = monotonic_ms() - dispatch_start_ms
        _record_dispatch_metrics(
            metrics_recorder=metrics_recorder,
            dispatch_duration_ms=dispatch_duration_ms,
            callback_count=callback_count,
        )
        if aggregate_timed_out:
            return DispatchCallbacksResult(
                aggregate_timed_out=True,
                failure_message=f"Aggregate dispatch timed out for {type(event).__name__}.",
            )
        _log_callback_result_exception(
            callback_result=result,
            callback=callback,
            event=event,
            logger=logger,
            trace_id=trace_id,
        )
        if isinstance(result, BaseException):
            return DispatchCallbacksResult(
                aggregate_timed_out=False,
                failure_message=(
                    f"Subscriber {describe_callback(callback)} failed for "
                    f"{type(event).__name__}."
                ),
            )
        return DispatchCallbacksResult(
            aggregate_timed_out=False,
            failure_message=quarantine_failure_message,
        )
    (
        aggregate_timed_out,
        results_by_task,
        tasks,
    ) = await dispatch_multiple_callbacks(
        callbacks=dispatchable_callbacks,
        event=event,
        logger=logger,
        dispatch_timeout=dispatch_timeout,
        per_callback_timeout=per_callback_timeout,
        stuck_callback_registry=stuck_callback_registry,
        metrics_recorder=metrics_recorder,
        finalizer_tracker=finalizer_tracker,
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id,
    )
    dispatch_duration_ms = monotonic_ms() - dispatch_start_ms
    _record_dispatch_metrics(
        metrics_recorder=metrics_recorder,
        dispatch_duration_ms=dispatch_duration_ms,
        callback_count=callback_count,
    )
    if aggregate_timed_out:
        return DispatchCallbacksResult(
            aggregate_timed_out=True,
            failure_message=f"Aggregate dispatch timed out for {type(event).__name__}.",
        )
    failure_message: str | None = None
    results = [results_by_task.get(task) for task in tasks]
    for callback, callback_result in zip(dispatchable_callbacks, results, strict=True):
        _log_callback_result_exception(
            callback_result=callback_result,
            callback=callback,
            event=event,
            logger=logger,
            trace_id=trace_id,
        )
        if failure_message is None and isinstance(callback_result, BaseException):
            failure_message = (
                f"Subscriber {describe_callback(callback)} failed for {type(event).__name__}."
            )
    if failure_message is None:
        failure_message = quarantine_failure_message
    return DispatchCallbacksResult(
        aggregate_timed_out=False,
        failure_message=failure_message,
    )
