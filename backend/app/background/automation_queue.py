"""SoAI - Automation run queue with overflow buffer [backend/app/background/automation_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque

from core.errors.exceptions import StateError

__all__ = ("AutomationRunQueue",)


class AutomationRunQueue:
    def __init__(self, maxsize: int) -> None:
        self._run_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=maxsize)
        self._queued_run_ids: set[str] = set()
        self._overflow_run_ids: set[str] = set()
        self._overflow_run_order: deque[str] = deque()

    @property
    def run_queue(self) -> asyncio.Queue[str]:
        return self._run_queue

    @property
    def queued_run_ids(self) -> set[str]:
        return self._queued_run_ids

    def reset(self, maxsize: int) -> None:
        self._run_queue = asyncio.Queue(maxsize=maxsize)
        self._queued_run_ids.clear()
        self._overflow_run_ids.clear()
        self._overflow_run_order.clear()

    def clear(self) -> None:
        self._queued_run_ids.clear()
        self._overflow_run_ids.clear()
        self._overflow_run_order.clear()

    def enqueue_run_id(self, run_id: str) -> None:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise StateError("Automation run id is invalid.")
        if normalized_run_id in self._queued_run_ids or normalized_run_id in self._overflow_run_ids:
            return
        try:
            self._run_queue.put_nowait(normalized_run_id)
        except asyncio.QueueFull:
            self._overflow_run_ids.add(normalized_run_id)
            self._overflow_run_order.append(normalized_run_id)
            return
        self._queued_run_ids.add(normalized_run_id)

    def refill_run_queue(self) -> None:
        while not self._run_queue.full() and self._overflow_run_order:
            run_id = self._overflow_run_order.popleft()
            if run_id not in self._overflow_run_ids:
                continue
            self._overflow_run_ids.discard(run_id)
            if run_id in self._queued_run_ids:
                continue
            try:
                self._run_queue.put_nowait(run_id)
            except asyncio.QueueFull:
                self._overflow_run_ids.add(run_id)
                self._overflow_run_order.appendleft(run_id)
                return
            self._queued_run_ids.add(run_id)
