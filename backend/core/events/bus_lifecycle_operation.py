"""SoAI - Event bus start and shutdown operation coordinators [backend/core/events/bus_lifecycle_operation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.queue_ops import QueueDropTracker
from core.events.bus_partitions import EventBusPartitions
from core.events.bus_queue_ops import settle_queued_events
from core.events.bus_sentinel import EventBusSentinel
from core.events.bus_shutdown import shutdown_worker_tasks
from core.events.bus_startup import start_event_bus_worker_tasks
from core.events.bus_stuck_callback_registry import EventBusStuckCallbackRegistry
from core.events.types_base import Event
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = (
    "execute_event_bus_shutdown",
    "execute_event_bus_start",
)


def _settle_partition_queues(
    partitions: EventBusPartitions,
    *,
    failure_message: str,
    logger: TraceLogger,
    reply_channel_drop_tracker: QueueDropTracker,
) -> int:
    return sum(
        settle_queued_events(
            queue,
            failure_message=failure_message,
            logger=logger,
            drop_tracker=reply_channel_drop_tracker,
        )
        for queue in partitions.queues
    )


def execute_event_bus_start(
    *,
    partitions: EventBusPartitions,
    shutdown_event: asyncio.Event,
    metrics_recorder: MetricsManagerProtocol | None,
    collect_callbacks: Callable[[Event], list[Callable[[Event], Awaitable[None]]]],
    dispatch_timeout: float | None,
    per_callback_timeout: float | None,
    logger: TraceLogger,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    stuck_callback_registry: EventBusStuckCallbackRegistry,
    reply_channel_drop_tracker: QueueDropTracker,
) -> None:
    if partitions.has_live_worker():
        logger.warning("EventBus start() called but workers are already running.")
        return
    if shutdown_event.is_set():
        shutdown_event.clear()
    discarded_count = _settle_partition_queues(
        partitions,
        failure_message="Event bus start discarded a queued event.",
        logger=logger,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
    )
    if discarded_count:
        logger.warning("EventBus start() discarded %s queued event(s).", discarded_count)
    partitions.rebuild()
    partitions.workers = start_event_bus_worker_tasks(
        queues=partitions.queues,
        shutdown_event=shutdown_event,
        metrics_recorder=metrics_recorder,
        collect_callbacks=collect_callbacks,
        dispatch_timeout=dispatch_timeout,
        per_callback_timeout=per_callback_timeout,
        logger=logger,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        stuck_callback_registry=stuck_callback_registry,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
    )
    logger.debug("EventBus started with %s worker tasks.", partitions.partition_count)


async def execute_event_bus_shutdown(
    *,
    partitions: EventBusPartitions,
    shutdown_event: asyncio.Event,
    shutdown_timeout: float,
    logger: TraceLogger,
    reply_channel_drop_tracker: QueueDropTracker,
) -> None:
    if shutdown_event.is_set():
        logger.debug("EventBus shutdown already initiated; completing worker shutdown.")
    else:
        logger.debug("EventBus shutdown initiated.")
        shutdown_event.set()
    await shutdown_worker_tasks(
        queues=partitions.queues,
        worker_tasks=partitions.workers,
        sentinel=EventBusSentinel,
        shutdown_timeout=shutdown_timeout,
        logger=logger,
    )
    discarded_count = _settle_partition_queues(
        partitions,
        failure_message="Event bus shutdown discarded a queued event.",
        logger=logger,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
    )
    if discarded_count:
        logger.debug(
            "EventBus shutdown settled %d queued event(s) as undelivered.", discarded_count
        )
    partitions.rebuild()
    logger.debug("EventBus has been shut down.")
