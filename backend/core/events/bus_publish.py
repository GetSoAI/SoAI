"""SoAI - Event bus publish flow and backpressure handling [backend/core/events/bus_publish.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.bus_partitioning import select_event_partition
from core.events.bus_publish_error_paths import (
    handle_publish_timeout_exception,
    reject_unavailable_partition,
)
from core.events.completion_signals import (
    mark_completion_signal_enqueued,
    mark_completion_signal_not_enqueued,
)
from core.events.protocols import EventCompletionSignal
from core.events.types_base import Event, EventDelivery
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.concurrency.queue_ops import QueueDropTracker
    from core.events.bus_backpressure import EventBusBackpressureTracker
    from core.events.bus_partitions import EventBusPartitions
    from core.events.bus_sentinel import EventBusSentinel
    from core.events.bus_worker import EventQueueItem
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = (
    "publish_event_to_partition",
    "try_publish_event_to_partition",
)

OPERATION_EVENT_BUS_PUBLISH = "event_bus.publish"
OPERATION_EVENT_BUS_TRY_PUBLISH_NOWAIT = "event_bus.try_publish_nowait"


def _record_queue_full(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    failure_message: str,
    partitions: EventBusPartitions,
    index: int,
    delivery: EventDelivery,
    backpressure_tracker: EventBusBackpressureTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> None:
    mark_completion_signal_not_enqueued(wait_for_completion, failure_message=failure_message)
    if delivery == EventDelivery.DROPPABLE:
        backpressure_tracker.record_publish_drop(
            event=event,
            reason="queue_full",
            pressure=partitions.pressure(index),
            metrics_recorder=metrics_recorder,
            logger=logger,
        )
        return
    backpressure_tracker.record_backpressure_state(
        queue_depth=partitions.depth(),
        logger=logger,
    )


def try_publish_event_to_partition(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    partitions: EventBusPartitions,
    queue_size: int,
    delivery: EventDelivery,
    backpressure_tracker: EventBusBackpressureTracker,
    reply_channel_drop_tracker: QueueDropTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> bool:
    index = select_event_partition(event=event, partitions=partitions)
    if not partitions.is_live(index):
        reject_unavailable_partition(
            event=event,
            delivery=delivery,
            wait_for_completion=wait_for_completion,
            pressure=partitions.pressure(index),
            raise_when_rejected=False,
            cause=None,
            backpressure_tracker=backpressure_tracker,
            metrics_recorder=metrics_recorder,
            logger=logger,
            reply_channel_drop_tracker=reply_channel_drop_tracker,
        )
        return False
    queue = partitions.queues[index]
    if queue_size and queue.full():
        failure_message = "Event bus queue was full before enqueue."
    else:
        try:
            queue.put_nowait((event, monotonic_ms(), wait_for_completion))
        except asyncio.QueueFull:
            failure_message = "Event bus queue was full during enqueue."
        except RECOVERABLE_EXCEPTIONS as exception:
            mark_completion_signal_not_enqueued(
                wait_for_completion,
                failure_message=f"Failed to publish event without waiting: {exception}",
            )
            log_exception(
                logger,
                exception,
                message="Failed to publish event without waiting",
                operation=OPERATION_EVENT_BUS_TRY_PUBLISH_NOWAIT,
                details={"event_type": type(event).__name__, "delivery": str(delivery)},
            )
            return False
        else:
            mark_completion_signal_enqueued(wait_for_completion)
            backpressure_tracker.record_backpressure_state(
                queue_depth=partitions.depth(),
                logger=logger,
            )
            return True
    _record_queue_full(
        event=event,
        wait_for_completion=wait_for_completion,
        failure_message=failure_message,
        partitions=partitions,
        index=index,
        delivery=delivery,
        backpressure_tracker=backpressure_tracker,
        metrics_recorder=metrics_recorder,
        logger=logger,
    )
    return False


async def _enqueue_event(
    *,
    event: Event,
    queue: asyncio.Queue[EventQueueItem | type[EventBusSentinel]],
    wait_for_completion: EventCompletionSignal | None,
    publish_timeout: float | None,
) -> None:
    try:
        async with asyncio.timeout(publish_timeout):
            await queue.put((event, monotonic_ms(), wait_for_completion))
    except asyncio.CancelledError:
        mark_completion_signal_not_enqueued(
            wait_for_completion,
            failure_message="Event bus publish was cancelled before enqueue completed.",
        )
        raise
    mark_completion_signal_enqueued(wait_for_completion)


async def publish_event_to_partition(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    partitions: EventBusPartitions,
    queue_size: int,
    publish_timeout: float | None,
    delivery: EventDelivery,
    backpressure_tracker: EventBusBackpressureTracker,
    reply_channel_drop_tracker: QueueDropTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> None:
    index = select_event_partition(event=event, partitions=partitions)
    queue = partitions.queues[index]
    unavailable_cause: asyncio.QueueShutDown | None = None
    if partitions.is_live(index):
        if queue_size and queue.full() and delivery == EventDelivery.DROPPABLE:
            _record_queue_full(
                event=event,
                wait_for_completion=wait_for_completion,
                failure_message="Droppable event was dropped because the queue was full.",
                partitions=partitions,
                index=index,
                delivery=delivery,
                backpressure_tracker=backpressure_tracker,
                metrics_recorder=metrics_recorder,
                logger=logger,
            )
            return
        try:
            await _enqueue_event(
                event=event,
                queue=queue,
                wait_for_completion=wait_for_completion,
                publish_timeout=publish_timeout,
            )
        except asyncio.QueueShutDown as exception:
            unavailable_cause = exception
        except TimeoutError as exception:
            handle_publish_timeout_exception(
                exception=exception,
                event=event,
                delivery=delivery,
                wait_for_completion=wait_for_completion,
                pressure=partitions.pressure(index),
                publish_timeout=publish_timeout,
                backpressure_tracker=backpressure_tracker,
                metrics_recorder=metrics_recorder,
                logger=logger,
                reply_channel_drop_tracker=reply_channel_drop_tracker,
            )
            return
        except RECOVERABLE_EXCEPTIONS as exception:
            mark_completion_signal_not_enqueued(
                wait_for_completion,
                failure_message=f"Failed to publish event: {exception}",
            )
            log_exception(
                logger,
                exception,
                message="Failed to publish event",
                operation=OPERATION_EVENT_BUS_PUBLISH,
                details={"event_type": type(event).__name__, "delivery": str(delivery)},
            )
            raise
        else:
            backpressure_tracker.record_backpressure_state(
                queue_depth=partitions.depth(),
                logger=logger,
            )
            return
    reject_unavailable_partition(
        event=event,
        delivery=delivery,
        wait_for_completion=wait_for_completion,
        pressure=partitions.pressure(index),
        raise_when_rejected=True,
        cause=unavailable_cause,
        backpressure_tracker=backpressure_tracker,
        metrics_recorder=metrics_recorder,
        logger=logger,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
    )
