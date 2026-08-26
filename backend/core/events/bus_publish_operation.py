"""SoAI - Event bus publish operation coordinator [backend/core/events/bus_publish_operation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.bus_publish import (
    publish_event_to_partition,
    try_publish_event_to_partition,
)
from core.events.bus_publish_guard import prepare_publish_worker_state
from core.events.protocols import EventCompletionSignal, EventWithDeliveryProtocol
from core.events.types_base import Event, EventDelivery

if TYPE_CHECKING:
    from core.concurrency.queue_ops import QueueDropTracker
    from core.events.bus_backpressure import EventBusBackpressureTracker
    from core.events.bus_sentinel import EventBusSentinel
    from core.events.bus_worker import EventQueueItem
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = (
    "execute_event_bus_publish",
    "try_execute_event_bus_publish_nowait",
)


async def execute_event_bus_publish(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    shutdown_event: asyncio.Event,
    worker_tasks: list[asyncio.Task[None]],
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    num_workers: int,
    round_robin_index: int,
    queue_size: int,
    publish_timeout: float | None,
    aggregate_queue_max: int,
    backpressure_tracker: EventBusBackpressureTracker,
    reply_channel_drop_tracker: QueueDropTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> tuple[list[asyncio.Task[None]], int]:
    active_worker_tasks = prepare_publish_worker_state(
        event=event,
        wait_for_completion=wait_for_completion,
        shutdown_event=shutdown_event,
        worker_tasks=worker_tasks,
        logger=logger,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
    )
    if not active_worker_tasks:
        return active_worker_tasks, round_robin_index
    delivery = (
        event.delivery
        if isinstance(event, EventWithDeliveryProtocol)
        else EventDelivery.MUST_DELIVER
    )
    next_round_robin_index = await publish_event_to_partition(
        event=event,
        wait_for_completion=wait_for_completion,
        queues=queues,
        num_workers=num_workers,
        round_robin_index=round_robin_index,
        queue_size=queue_size,
        publish_timeout=publish_timeout,
        aggregate_queue_max=aggregate_queue_max,
        delivery=delivery,
        backpressure_tracker=backpressure_tracker,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
        metrics_recorder=metrics_recorder,
        logger=logger,
    )
    return active_worker_tasks, next_round_robin_index


def try_execute_event_bus_publish_nowait(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    shutdown_event: asyncio.Event,
    worker_tasks: list[asyncio.Task[None]],
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    num_workers: int,
    round_robin_index: int,
    queue_size: int,
    backpressure_tracker: EventBusBackpressureTracker,
    reply_channel_drop_tracker: QueueDropTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> tuple[bool, list[asyncio.Task[None]], int]:
    active_worker_tasks = prepare_publish_worker_state(
        event=event,
        wait_for_completion=wait_for_completion,
        shutdown_event=shutdown_event,
        worker_tasks=worker_tasks,
        logger=logger,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
        raise_when_not_running=False,
        notify_reply_channel=False,
    )
    if not active_worker_tasks:
        return False, active_worker_tasks, round_robin_index
    delivery = (
        event.delivery
        if isinstance(event, EventWithDeliveryProtocol)
        else EventDelivery.MUST_DELIVER
    )
    published, next_round_robin_index = try_publish_event_to_partition(
        event=event,
        wait_for_completion=wait_for_completion,
        queues=queues,
        num_workers=num_workers,
        round_robin_index=round_robin_index,
        queue_size=queue_size,
        delivery=delivery,
        backpressure_tracker=backpressure_tracker,
        metrics_recorder=metrics_recorder,
        logger=logger,
    )
    return published, active_worker_tasks, next_round_robin_index
