"""SoAI - Queue operation helpers [backend/core/concurrency/queue_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.concurrency.queue_drop_tracking import (
    QueueDropReport,
    QueueDropTracker,
    log_queue_drop_with_tracker,
)

__all__ = (
    "OverwriteDeliveryResult",
    "QueueDropReport",
    "QueueDropTracker",
    "drain_queue_to_list",
    "log_queue_drop_with_tracker",
    "put_nowait_with_overwrite",
)


@dataclass(frozen=True, slots=True)
class OverwriteDeliveryResult:
    delivered: bool
    dropped_count: int


def drain_queue_to_list[T](queue: asyncio.Queue[T], *, mark_tasks_done: bool = True) -> list[T]:
    items: list[T] = []
    while True:
        try:
            item = queue.get_nowait()
            if mark_tasks_done:
                queue.task_done()
        except asyncio.QueueEmpty:
            break
        items.append(item)
    return items


def put_nowait_with_overwrite[T](
    queue: asyncio.Queue[T] | None,
    event: T,
    *,
    overwrite_attempts: int = 1,
) -> OverwriteDeliveryResult:
    if queue is None:
        return OverwriteDeliveryResult(delivered=False, dropped_count=0)
    attempts = max(0, int(overwrite_attempts))
    try:
        queue.put_nowait(event)
        return OverwriteDeliveryResult(delivered=True, dropped_count=0)
    except asyncio.QueueFull:
        dropped = 0
        for _ in range(attempts):
            try:
                queue.get_nowait()
                queue.task_done()
                dropped += 1
            except asyncio.QueueEmpty:
                break
            try:
                queue.put_nowait(event)
                return OverwriteDeliveryResult(delivered=True, dropped_count=dropped)
            except asyncio.QueueFull:
                continue
        try:
            queue.put_nowait(event)
            return OverwriteDeliveryResult(delivered=True, dropped_count=dropped)
        except asyncio.QueueFull:
            return OverwriteDeliveryResult(delivered=False, dropped_count=dropped)
