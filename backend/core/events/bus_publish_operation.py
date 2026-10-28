"""SoAI - Event bus publish operation coordinator [backend/core/events/bus_publish_operation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.bus_publish import (
    publish_event_to_partition,
    try_publish_event_to_partition,
)
from core.events.bus_publish_guard import admit_event_bus_publication
from core.events.protocols import EventCompletionSignal, EventWithDeliveryProtocol
from core.events.types_base import Event, EventDelivery

if TYPE_CHECKING:
    from core.concurrency.queue_ops import QueueDropTracker
    from core.events.bus_backpressure import EventBusBackpressureTracker
    from core.events.bus_partitions import EventBusPartitions
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = (
    "execute_event_bus_publish",
    "try_execute_event_bus_publish_nowait",
)


def _resolve_delivery(event: Event) -> EventDelivery:
    if isinstance(event, EventWithDeliveryProtocol):
        return event.delivery
    return EventDelivery.MUST_DELIVER


async def execute_event_bus_publish(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    shutdown_event: asyncio.Event,
    partitions: EventBusPartitions,
    queue_size: int,
    publish_timeout: float | None,
    backpressure_tracker: EventBusBackpressureTracker,
    reply_channel_drop_tracker: QueueDropTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> None:
    if not admit_event_bus_publication(
        event=event,
        wait_for_completion=wait_for_completion,
        shutdown_event=shutdown_event,
        partitions=partitions,
        logger=logger,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
    ):
        return
    await publish_event_to_partition(
        event=event,
        wait_for_completion=wait_for_completion,
        partitions=partitions,
        queue_size=queue_size,
        publish_timeout=publish_timeout,
        delivery=_resolve_delivery(event),
        backpressure_tracker=backpressure_tracker,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
        metrics_recorder=metrics_recorder,
        logger=logger,
    )


def try_execute_event_bus_publish_nowait(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    shutdown_event: asyncio.Event,
    partitions: EventBusPartitions,
    queue_size: int,
    backpressure_tracker: EventBusBackpressureTracker,
    reply_channel_drop_tracker: QueueDropTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> bool:
    if not admit_event_bus_publication(
        event=event,
        wait_for_completion=wait_for_completion,
        shutdown_event=shutdown_event,
        partitions=partitions,
        logger=logger,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
        raise_when_not_running=False,
        notify_reply_channel=False,
    ):
        return False
    return try_publish_event_to_partition(
        event=event,
        wait_for_completion=wait_for_completion,
        partitions=partitions,
        queue_size=queue_size,
        delivery=_resolve_delivery(event),
        backpressure_tracker=backpressure_tracker,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
        metrics_recorder=metrics_recorder,
        logger=logger,
    )
