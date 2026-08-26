"""SoAI - Event bus start and shutdown operation coordinators [backend/core/events/bus_lifecycle_operation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.events.bus_partitions import (
    build_partition_queues,
    drain_orphaned_completion_events,
    prune_inactive_worker_tasks,
)
from core.events.bus_sentinel import EventBusSentinel
from core.events.bus_shutdown import shutdown_worker_tasks
from core.events.bus_startup import start_event_bus_worker_tasks
from core.events.bus_stuck_callback_registry import EventBusStuckCallbackRegistry
from core.events.completion_signals import mark_completion_signal_not_enqueued
from core.events.types_base import Event
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.events.bus_worker import EventQueueItem
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = (
    "execute_event_bus_shutdown",
    "execute_event_bus_start",
)


def execute_event_bus_start(
    *,
    worker_tasks: list[asyncio.Task[None]],
    shutdown_event: asyncio.Event,
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    num_workers: int,
    queue_max_per_worker: int,
    metrics_recorder: MetricsManagerProtocol | None,
    collect_callbacks: Callable[[Event], list[Callable[[Event], Awaitable[None]]]],
    dispatch_timeout: float | None,
    per_callback_timeout: float | None,
    logger: TraceLogger,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    stuck_callback_registry: EventBusStuckCallbackRegistry,
) -> tuple[
    list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    list[asyncio.Task[None]],
    int,
]:
    active_worker_tasks = prune_inactive_worker_tasks(worker_tasks)
    if active_worker_tasks:
        logger.warning("EventBus start() called but workers are already running.")
        return queues, active_worker_tasks, 0
    if shutdown_event.is_set():
        shutdown_event.clear()
    queued_count = sum(queue.qsize() for queue in queues)
    if queued_count:
        logger.warning("EventBus start() discarding %s queued event(s).", queued_count)
        orphaned_completion_events = drain_orphaned_completion_events(
            queues=queues,
            sentinel=EventBusSentinel,
        )
        for completion_event in orphaned_completion_events:
            mark_completion_signal_not_enqueued(
                completion_event,
                failure_message="Event bus start discarded queued completion signal.",
            )
        if orphaned_completion_events:
            logger.debug(
                "EventBus start() signaled %d orphaned completion event_types.",
                len(orphaned_completion_events),
            )
    rebuilt_queues = build_partition_queues(
        num_workers=num_workers,
        queue_max_per_worker=queue_max_per_worker,
    )
    started_worker_tasks = start_event_bus_worker_tasks(
        num_workers=num_workers,
        queues=rebuilt_queues,
        metrics_recorder=metrics_recorder,
        collect_callbacks=collect_callbacks,
        dispatch_timeout=dispatch_timeout,
        per_callback_timeout=per_callback_timeout,
        logger=logger,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        stuck_callback_registry=stuck_callback_registry,
    )
    logger.debug("EventBus started with %s worker tasks.", num_workers)
    return rebuilt_queues, started_worker_tasks, 0


async def execute_event_bus_shutdown(
    *,
    shutdown_event: asyncio.Event,
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    worker_tasks: list[asyncio.Task[None]],
    shutdown_timeout: float,
    num_workers: int,
    queue_max_per_worker: int,
    logger: TraceLogger,
) -> tuple[list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]], int]:
    if shutdown_event.is_set():
        logger.debug("EventBus shutdown already initiated; completing worker shutdown.")
    else:
        logger.debug("EventBus shutdown initiated.")
        shutdown_event.set()
    await shutdown_worker_tasks(
        queues=queues,
        worker_tasks=worker_tasks,
        sentinel=EventBusSentinel,
        shutdown_timeout=shutdown_timeout,
        logger=logger,
    )
    orphaned_completion_events = drain_orphaned_completion_events(
        queues=queues,
        sentinel=EventBusSentinel,
    )
    for completion_event in orphaned_completion_events:
        mark_completion_signal_not_enqueued(
            completion_event,
            failure_message="Event bus shutdown discarded queued completion signal.",
        )
    rebuilt_queues = build_partition_queues(
        num_workers=num_workers,
        queue_max_per_worker=queue_max_per_worker,
    )
    logger.debug("EventBus has been shut down.")
    return rebuilt_queues, 0
