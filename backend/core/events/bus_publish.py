"""SoAI - Event bus publish flow and backpressure handling [backend/core/events/bus_publish.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.bus_partitioning import queue_for_event
from core.events.bus_partitions import aggregate_queue_depth
from core.events.bus_publish_error_paths import handle_publish_timeout_exception
from core.events.bus_sentinel import EventBusSentinel
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
    from core.events.bus_worker import EventQueueItem
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = (
    "publish_event_to_partition",
    "try_publish_event_to_partition",
)

OPERATION_EVENT_BUS_PUBLISH = "event_bus.publish"
OPERATION_EVENT_BUS_TRY_PUBLISH_NOWAIT = "event_bus.try_publish_nowait"


def try_publish_event_to_partition(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    num_workers: int,
    round_robin_index: int,
    queue_size: int,
    delivery: EventDelivery,
    backpressure_tracker: EventBusBackpressureTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> tuple[bool, int]:
    queue, next_round_robin_index = queue_for_event(
        event=event,
        queues=queues,
        num_workers=num_workers,
        round_robin_index=round_robin_index,
    )
    queue_depth = aggregate_queue_depth(queues)
    if queue_size and queue.full():
        mark_completion_signal_not_enqueued(
            wait_for_completion,
            failure_message="Event bus queue was full before enqueue.",
        )
        if delivery == EventDelivery.DROPPABLE:
            backpressure_tracker.record_publish_drop(
                event=event,
                reason="queue_full",
                queue_depth=queue_depth,
                metrics_recorder=metrics_recorder,
                logger=logger,
            )
        else:
            backpressure_tracker.record_backpressure_state(
                queue_depth=queue_depth,
                logger=logger,
            )
        return False, next_round_robin_index
    try:
        queue.put_nowait((event, monotonic_ms(), wait_for_completion))
    except asyncio.QueueFull:
        mark_completion_signal_not_enqueued(
            wait_for_completion,
            failure_message="Event bus queue was full during enqueue.",
        )
        queue_depth = aggregate_queue_depth(queues)
        if delivery == EventDelivery.DROPPABLE:
            backpressure_tracker.record_publish_drop(
                event=event,
                reason="queue_full",
                queue_depth=queue_depth,
                metrics_recorder=metrics_recorder,
                logger=logger,
            )
        else:
            backpressure_tracker.record_backpressure_state(
                queue_depth=queue_depth,
                logger=logger,
            )
        return False, next_round_robin_index
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
        return False, next_round_robin_index
    backpressure_tracker.record_backpressure_state(
        queue_depth=aggregate_queue_depth(queues),
        logger=logger,
    )
    mark_completion_signal_enqueued(wait_for_completion)
    return True, next_round_robin_index


async def publish_event_to_partition(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    num_workers: int,
    round_robin_index: int,
    queue_size: int,
    publish_timeout: float | None,
    aggregate_queue_max: int,
    delivery: EventDelivery,
    backpressure_tracker: EventBusBackpressureTracker,
    reply_channel_drop_tracker: QueueDropTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> int:
    queue, next_round_robin_index = queue_for_event(
        event=event,
        queues=queues,
        num_workers=num_workers,
        round_robin_index=round_robin_index,
    )
    if queue_size and queue.full() and delivery == EventDelivery.DROPPABLE:
        backpressure_tracker.record_publish_drop(
            event=event,
            reason="queue_full",
            queue_depth=aggregate_queue_depth(queues),
            metrics_recorder=metrics_recorder,
            logger=logger,
        )
        mark_completion_signal_not_enqueued(
            wait_for_completion,
            failure_message="Droppable event was dropped because the queue was full.",
        )
        return next_round_robin_index
    try:
        coro = queue.put((event, monotonic_ms(), wait_for_completion))
        if publish_timeout is not None:
            await asyncio.wait_for(coro, timeout=publish_timeout)
        else:
            await coro
        mark_completion_signal_enqueued(wait_for_completion)
    except TimeoutError as exception:
        queue_depth = aggregate_queue_depth(queues)
        handle_publish_timeout_exception(
            exception=exception,
            event=event,
            delivery=delivery,
            wait_for_completion=wait_for_completion,
            queue_depth=queue_depth,
            aggregate_queue_max=aggregate_queue_max,
            publish_timeout=publish_timeout,
            backpressure_tracker=backpressure_tracker,
            metrics_recorder=metrics_recorder,
            logger=logger,
            reply_channel_drop_tracker=reply_channel_drop_tracker,
        )
        if delivery == EventDelivery.DROPPABLE:
            return next_round_robin_index
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
    backpressure_tracker.record_backpressure_state(
        queue_depth=aggregate_queue_depth(queues),
        logger=logger,
    )
    return next_round_robin_index
