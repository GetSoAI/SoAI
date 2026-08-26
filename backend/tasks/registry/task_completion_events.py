"""SoAI - Task registry completion event tracking [backend/tasks/registry/task_completion_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exceptions import ServiceUnavailableError
from core.logging.trace import get_logger

__all__ = ("TaskCompletionEvents",)

LOGGER_NAME = "SoAI.tasks.registry.task_completion_events"


MAX_SIZE_WARNING_THRESHOLD_MULTIPLIER: float = 1.5


class TaskCompletionEvents:

    def __init__(self, *, max_size: int) -> None:
        self.lock = asyncio.Lock()
        self.events: dict[str, asyncio.Event] = {}
        self._waiter_counts: dict[str, int] = {}
        self._max_size = int(max_size)
        self._warning_threshold = int(self._max_size * MAX_SIZE_WARNING_THRESHOLD_MULTIPLIER)
        self._threshold_warned = False

    async def ensure(self, task_id: str, *, set_if_terminal: bool) -> asyncio.Event:
        async with self.lock:
            event = self.events.get(task_id)
            if set_if_terminal:
                if event is not None:
                    event.set()
                    self.events.pop(task_id, None)
                    self._waiter_counts.pop(task_id, None)
                    return event
                terminal_event = asyncio.Event()
                terminal_event.set()
                return terminal_event
            if event is None:
                self._evict_if_needed()
                event = asyncio.Event()
                self.events[task_id] = event
                self._waiter_counts[task_id] = 1
                return event
            self._waiter_counts[task_id] = self._waiter_counts.get(task_id, 0) + 1
            return event

    async def release(self, task_id: str) -> None:
        async with self.lock:
            count = self._waiter_counts.get(task_id, 0)
            if count <= 1:
                self._waiter_counts.pop(task_id, None)
                self.events.pop(task_id, None)
                return
            self._waiter_counts[task_id] = count - 1

    async def clear(self, task_id: str) -> None:
        async with self.lock:
            event = self.events.pop(task_id, None)
            self._waiter_counts.pop(task_id, None)
            if event is not None:
                event.set()

    def _evict_if_needed(self) -> None:
        current_size = len(self.events)
        if current_size >= self._warning_threshold and not self._threshold_warned:
            self._threshold_warned = True
            logger = get_logger(LOGGER_NAME)
            logger.warning(
                "TaskCompletionEvents size (%d) exceeds warning threshold (%d). Eviction only removes completed events; in-flight events are preserved.",
                current_size,
                self._warning_threshold,
            )
        if current_size < self._max_size:
            if current_size < self._warning_threshold:
                self._threshold_warned = False
            return
        set_event_ids = [tid for tid, evt in self.events.items() if evt.is_set()]
        for tid in set_event_ids[: max(1, len(set_event_ids) // 2)]:
            self.events.pop(tid, None)
            self._waiter_counts.pop(tid, None)
        if len(self.events) >= self._max_size:
            raise ServiceUnavailableError(
                f"Too many concurrent task completion waiters ({len(self.events)} >= {self._max_size}).",
            )
