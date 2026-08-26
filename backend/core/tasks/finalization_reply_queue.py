"""SoAI - Task finalization reply-queue completion delivery [backend/core/tasks/finalization_reply_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.events.types_tasks import TaskCompleteEvent
from core.logging.protocols import StandardLogger
from core.tasks.task import Task
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from core.timing.constants import MODERATE_DELAY_SEC

__all__ = ("deliver_completion_event_to_reply_queue",)


async def deliver_completion_event_to_reply_queue(
    *,
    logger: StandardLogger,
    task: Task,
    completion_event: TaskCompleteEvent,
) -> Task:
    reply_queue = task.reply_queue
    if reply_queue is None:
        return task
    if not is_orchestrated_inference_task_type(task.task_type):
        try:
            await asyncio.wait_for(
                reply_queue.put(completion_event),
                timeout=MODERATE_DELAY_SEC,
            )
        except TimeoutError:
            logger.warning(
                "Reply queue blocked when sending completion for task %s after %.1fs",
                task.task_id,
                MODERATE_DELAY_SEC,
            )
    task_without_queue, _ = task.without_reply_queue()
    return task_without_queue
