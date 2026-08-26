"""SoAI - Scheduler waiter pending queue restoration [backend/orchestrator/scheduling/waiter_pending_restoration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.orchestrator.protocols_queue import QueueTrackingViewProtocol
from core.tasks.task import Task

__all__ = ("restore_unscheduled_waiters",)


async def restore_unscheduled_waiters(
    *,
    tracking: QueueTrackingViewProtocol,
    tasks_to_process: list[Task],
    scheduled_count: int,
    pending_key: str,
    plugin_name: str,
) -> None:
    for task in reversed(tasks_to_process[scheduled_count:]):
        await asyncio.shield(
            tracking.register_pending_task(
                task,
                pending_key,
                plugin_name=plugin_name,
                insert_left=True,
            ),
        )
