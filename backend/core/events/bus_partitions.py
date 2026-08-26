"""SoAI - Event bus partition queue state helpers [backend/core/events/bus_partitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.bus_queue_ops import drain_queue_orphaned_completion_events
from core.events.protocols import EventCompletionSignal

if TYPE_CHECKING:
    from core.events.bus_sentinel import EventBusSentinel
    from core.events.bus_worker import EventQueueItem

__all__ = (
    "aggregate_queue_depth",
    "build_partition_queues",
    "drain_orphaned_completion_events",
    "prune_inactive_worker_tasks",
)


def build_partition_queues(
    *,
    num_workers: int,
    queue_max_per_worker: int,
) -> list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]]:
    return [asyncio.Queue(maxsize=queue_max_per_worker) for _ in range(num_workers)]


def aggregate_queue_depth(
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
) -> int:
    return sum(queue.qsize() for queue in queues)


def drain_orphaned_completion_events(
    *,
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    sentinel: type[EventBusSentinel],
) -> list[EventCompletionSignal]:
    orphaned_completion_events: list[EventCompletionSignal] = []
    for queue in queues:
        orphaned_completion_events.extend(drain_queue_orphaned_completion_events(queue, sentinel))
    return orphaned_completion_events


def prune_inactive_worker_tasks(worker_tasks: list[asyncio.Task[None]]) -> list[asyncio.Task[None]]:
    return [task for task in worker_tasks if not task.done()]
