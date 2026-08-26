"""SoAI - Async inference task priority queue [backend/orchestrator/queueing/inference_priority_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import heapq
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import override

from core.errors.exceptions import StateError
from core.orchestrator.request_priority import (
    RequestPriority,
    RequestSchedulingKey,
)
from core.tasks.task import Task
from core.validation.integers import is_strict_int
from orchestrator.queueing.request_scheduling import request_scheduling_key

__all__ = ("InferencePriorityQueue",)


@dataclass(frozen=True, order=True, slots=True)
class _PriorityQueueEntry[T]:
    scheduling_key: RequestSchedulingKey
    enqueue_sequence: int
    item: T = field(compare=False)


class InferencePriorityQueue[T](asyncio.Queue[T]):
    def __init__(
        self,
        maxsize: int = 0,
        *,
        resolve_task: Callable[[T], Task | None] | None = None,
    ) -> None:
        self._queue: list[_PriorityQueueEntry[T]] = []
        self._resolve_task = resolve_task
        self._enqueue_sequence = 0
        self._priority_counts = {priority: 0 for priority in RequestPriority}
        self._maxsize: int = maxsize
        self._putters: deque[asyncio.Future[None]] = deque()
        super().__init__(maxsize=maxsize)

    def resize(self, maxsize: int) -> None:
        if not is_strict_int(maxsize) or maxsize < 0:
            raise StateError(
                "Inference priority queue maxsize must be an integer greater than or equal to zero."
            )
        self._maxsize = maxsize
        available_slots = len(self._putters) if maxsize == 0 else max(maxsize - self.qsize(), 0)
        for _ in range(min(available_slots, len(self._putters))):
            self._wake_next_putter()

    def _wake_next_putter(self) -> None:
        while self._putters:
            putter = self._putters.popleft()
            if not putter.done():
                putter.set_result(None)
                return

    @override
    def _init(self, maxsize: int) -> None:
        _ = maxsize
        self._queue = []

    def _resolve_item_task(self, item: T) -> Task | None:
        if self._resolve_task is not None:
            return self._resolve_task(item)
        if isinstance(item, Task):
            return item
        raise StateError("Inference priority queue item is not an orchestrated task.")

    @override
    def _put(self, item: T) -> None:
        task = self._resolve_item_task(item)
        if task is None:
            scheduling_key = RequestSchedulingKey(
                priority_order=float("inf"),
                queued_at=float("inf"),
                task_id="",
            )
        else:
            task_scheduling_key = request_scheduling_key(task)
            scheduling_key = RequestSchedulingKey(
                priority_order=task_scheduling_key.priority_order,
                queued_at=task_scheduling_key.queued_at,
                task_id="",
            )
            priority = task.require_orchestration_context().priority_assignment.priority
            self._priority_counts[priority] += 1
        entry = _PriorityQueueEntry(
            scheduling_key=scheduling_key,
            enqueue_sequence=self._enqueue_sequence,
            item=item,
        )
        self._enqueue_sequence += 1
        heapq.heappush(self._queue, entry)

    @override
    def _get(self) -> T:
        entry = heapq.heappop(self._queue)
        task = self._resolve_item_task(entry.item)
        if task is not None:
            priority = task.require_orchestration_context().priority_assignment.priority
            self._priority_counts[priority] -= 1
        return entry.item

    def priority_counts(self) -> dict[RequestPriority, int]:
        return dict(self._priority_counts)
