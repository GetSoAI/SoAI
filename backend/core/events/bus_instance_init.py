"""SoAI - Event bus instance initialization helpers [backend/core/events/bus_instance_init.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.bus_backpressure import EventBusBackpressureTracker
from core.events.bus_constructor import EventBusConstructorValues
from core.events.bus_partitions import build_partition_queues
from core.events.bus_sentinel import EventBusSentinel
from core.metrics.protocols import MetricsManagerProtocol

if TYPE_CHECKING:
    from core.events.bus_worker import EventQueueItem

__all__ = (
    "EventBusInitializedState",
    "initialize_event_bus_state",
)


@dataclass(frozen=True, slots=True)
class EventBusInitializedState:
    queue_size: int
    num_workers: int
    queue_max_per_worker: int
    aggregate_queue_max: int
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]]
    publish_timeout: float | None
    backpressure_warning_depth: int | None
    dispatch_timeout: float | None
    shutdown_timeout: float
    per_callback_timeout: float | None
    backpressure_tracker: EventBusBackpressureTracker


def initialize_event_bus_state(
    *,
    constructor_values: EventBusConstructorValues,
    metrics_recorder: MetricsManagerProtocol | None,
) -> EventBusInitializedState:
    _ = metrics_recorder
    queue_max_per_worker = (
        constructor_values.queue_size + constructor_values.num_workers - 1
    ) // constructor_values.num_workers
    aggregate_queue_max = queue_max_per_worker * constructor_values.num_workers
    return EventBusInitializedState(
        queue_size=constructor_values.queue_size,
        num_workers=constructor_values.num_workers,
        queue_max_per_worker=queue_max_per_worker,
        aggregate_queue_max=aggregate_queue_max,
        queues=build_partition_queues(
            num_workers=constructor_values.num_workers,
            queue_max_per_worker=queue_max_per_worker,
        ),
        publish_timeout=constructor_values.publish_timeout,
        backpressure_warning_depth=constructor_values.backpressure_warning_depth,
        dispatch_timeout=constructor_values.dispatch_timeout,
        shutdown_timeout=constructor_values.shutdown_timeout,
        per_callback_timeout=constructor_values.per_callback_timeout,
        backpressure_tracker=EventBusBackpressureTracker(
            queue_size=aggregate_queue_max,
            backpressure_warning_depth=constructor_values.backpressure_warning_depth,
        ),
    )
