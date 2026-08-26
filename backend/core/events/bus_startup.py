"""SoAI - Event bus worker task startup helpers [backend/core/events/bus_startup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.events.bus_sentinel import EventBusSentinel
from core.events.bus_stuck_callback_registry import EventBusStuckCallbackRegistry
from core.events.bus_worker import run_event_bus_worker
from core.events.types_base import Event
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.events.bus_worker import EventQueueItem
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = ("start_event_bus_worker_tasks",)


def start_event_bus_worker_tasks(
    *,
    num_workers: int,
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    metrics_recorder: MetricsManagerProtocol | None,
    collect_callbacks: Callable[[Event], list[Callable[[Event], Awaitable[None]]]],
    dispatch_timeout: float | None,
    per_callback_timeout: float | None,
    logger: TraceLogger,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    stuck_callback_registry: EventBusStuckCallbackRegistry,
) -> list[asyncio.Task[None]]:
    worker_tasks: list[asyncio.Task[None]] = []
    for worker_id in range(num_workers):
        worker_tasks.append(
            spawn_tracked_task(
                run_event_bus_worker(
                    worker_id=worker_id,
                    queue=queues[worker_id],
                    sentinel=EventBusSentinel,
                    metrics_recorder=metrics_recorder,
                    collect_callbacks=collect_callbacks,
                    dispatch_timeout=dispatch_timeout,
                    per_callback_timeout=per_callback_timeout,
                    logger=logger,
                    stuck_callback_registry=stuck_callback_registry,
                    finalizer_tracker=finalizer_tracker,
                    cancellation_binder=cancellation_binder,
                ),
                name=f"event-bus-worker-{worker_id}",
                logger=logger,
                cancellation_binder=cancellation_binder,
                finalizer_tracker=finalizer_tracker,
                cancellation_id=build_soai_id(
                    ("sys", "event_bus", "worker", safe_or_hashed_segment(str(worker_id))),
                ),
                owner="event_bus_worker",
                metadata={"worker_id": worker_id},
            ),
        )
    return worker_tasks
