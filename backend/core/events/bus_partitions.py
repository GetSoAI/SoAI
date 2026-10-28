"""SoAI - Event bus partition queue state helpers [backend/core/events/bus_partitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.events.bus_sentinel import EventBusSentinel
    from core.events.bus_worker import EventQueueItem
    from core.types.json import JSONDict

__all__ = (
    "EventBusPartitions",
    "EventBusQueuePressure",
)


@dataclass(frozen=True, slots=True)
class EventBusQueuePressure:
    partition_index: int | None
    partition_depth: int
    partition_capacity: int
    aggregate_depth: int
    aggregate_capacity: int

    def describe(self) -> str:
        aggregate = f"aggregate depth={self.aggregate_depth}/{self.aggregate_capacity}"
        if self.partition_index is None:
            return aggregate
        return (
            f"partition {self.partition_index} depth="
            f"{self.partition_depth}/{self.partition_capacity}, {aggregate}"
        )

    def details(self) -> JSONDict:
        return {
            "partition_index": self.partition_index,
            "partition_depth": self.partition_depth,
            "partition_capacity": self.partition_capacity,
            "queue_depth": self.aggregate_depth,
            "queue_max": self.aggregate_capacity,
        }


class EventBusPartitions:
    __slots__ = ("cursor", "partition_count", "queue_max_per_worker", "queues", "workers")

    def __init__(self, *, partition_count: int, queue_max_per_worker: int) -> None:
        self.partition_count = partition_count
        self.queue_max_per_worker = queue_max_per_worker
        self.queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]] = []
        self.workers: list[asyncio.Task[None]] = []
        self.cursor = 0
        self.rebuild()

    def rebuild(self) -> None:
        self.queues = [
            asyncio.Queue(maxsize=self.queue_max_per_worker) for _ in range(self.partition_count)
        ]
        self.cursor = 0

    def is_live(self, index: int) -> bool:
        return index < len(self.workers) and not self.workers[index].done()

    def has_live_worker(self) -> bool:
        return any(not worker.done() for worker in self.workers)

    def depth(self) -> int:
        return sum(queue.qsize() for queue in self.queues)

    def pressure(self, index: int | None) -> EventBusQueuePressure:
        return EventBusQueuePressure(
            partition_index=index,
            partition_depth=0 if index is None else self.queues[index].qsize(),
            partition_capacity=self.queue_max_per_worker,
            aggregate_depth=self.depth(),
            aggregate_capacity=self.queue_max_per_worker * self.partition_count,
        )
