"""SoAI - Scheduler wake-set and batch collection [backend/orchestrator/scheduling/work_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exceptions import StateError
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_ALL,
    SchedulerWorkItem,
)
from core.timing.constants import SHORT_POLL_INTERVAL_SEC

__all__ = ("SchedulerWorkQueueState",)


class SchedulerWorkQueueState:
    def __init__(self) -> None:
        self._work_items: dict[tuple[str, str], SchedulerWorkItem] = {}
        self._work_event = asyncio.Event()
        self._work_lock = asyncio.Lock()
        self._last_log_time = 0.0
        self._safety_net_scheduled: bool = False
        self._safety_net_lock = asyncio.Lock()

    @property
    def pending_count(self) -> int:
        return len(self._work_items)

    async def enqueue_work(self, work_item: SchedulerWorkItem) -> None:
        async with self._work_lock:
            self._work_items[(work_item.work_type, work_item.key)] = work_item
            self._work_event.set()

    async def await_work_batch(
        self,
    ) -> tuple[SchedulerWorkItem, set[SchedulerWorkItem], float]:
        await asyncio.wait_for(
            self._work_event.wait(),
            timeout=SHORT_POLL_INTERVAL_SEC,
        )
        async with self._work_lock:
            if not self._work_items:
                self._work_event.clear()
                raise StateError("Scheduler work wake received without queued work items.")
            work_items = set(self._work_items.values())
            self._work_items.clear()
            self._work_event.clear()
        first_item = next(iter(work_items), None)
        if first_item is None:
            raise StateError("Scheduler work batch could not resolve a first item.")
        return (first_item, work_items, self._last_log_time)

    def update_log_time(self, timestamp: float) -> None:
        self._last_log_time = timestamp

    async def schedule_safety_net(self) -> bool:
        async with self._safety_net_lock:
            if self._safety_net_scheduled:
                return False
            self._safety_net_scheduled = True
            return True

    async def clear_safety_net_flag(self) -> None:
        async with self._safety_net_lock:
            self._safety_net_scheduled = False

    async def delayed_work_enqueue(self, delay: float, work_item: SchedulerWorkItem) -> None:
        await asyncio.sleep(float(delay))
        await self.enqueue_work(work_item)

    async def safety_net_cycle(self, delay: float) -> None:
        try:
            await self.delayed_work_enqueue(
                delay,
                SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_ALL, "safety_net"),
            )
        finally:
            await self.clear_safety_net_flag()
