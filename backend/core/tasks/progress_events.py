"""SoAI - Task progress event emission helpers [backend/core/tasks/progress_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.events.types_tasks import TaskProgressEvent
from core.logging.protocols import StandardLogger
from core.progress.percent import clamp_percent
from core.tasks.notifications import publish_event
from core.tasks.progress_details import serialize_progress_details
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.task import Task

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "compute_progress_percent",
    "emit_task_progress_event",
    "emit_task_progress_event_for_task",
    "emit_task_progress_event_for_task_with_details_str",
)


def compute_progress_percent(
    progress_current: int,
    progress_total: int | None,
    percent_override: int | None,
) -> int:
    if percent_override is not None:
        return clamp_percent(percent_override)
    if progress_total is not None and progress_total > 0:
        return clamp_percent(int(progress_current / progress_total * 100))
    return clamp_percent(progress_current)


async def emit_task_progress_event(
    registry: TaskRegistryLifecycleView,
    *,
    task: Task,
    task_id: str,
    progress_current: int,
    status_message: str | None,
    details_str: str,
    percent_override: int | None,
    logger: StandardLogger,
) -> None:
    percent = compute_progress_percent(progress_current, task.progress_total, percent_override)
    event = TaskProgressEvent(
        percent=percent,
        message=status_message or "",
        details=details_str,
        task_id=task_id,
        user_id=task.user_id,
    )
    await publish_event(registry.event_bus, event, "TaskProgressEvent")
    reply_queue = task.reply_queue
    if reply_queue is not None:
        if not put_nowait_with_overwrite(reply_queue, event, overwrite_attempts=1).delivered:
            logger.warning("Reply queue full when sending progress for task %s", task_id)


async def emit_task_progress_event_for_task(
    registry: TaskRegistryLifecycleView,
    *,
    task: Task,
    progress_current: int,
    status_message: str | None,
    details: JSONValue | None,
    percent_override: int | None,
    logger: StandardLogger,
) -> None:
    details_str = serialize_progress_details(details)
    await emit_task_progress_event(
        registry,
        task=task,
        task_id=task.task_id,
        progress_current=progress_current,
        status_message=status_message,
        details_str=details_str,
        percent_override=percent_override,
        logger=logger,
    )


async def emit_task_progress_event_for_task_with_details_str(
    registry: TaskRegistryLifecycleView,
    *,
    task: Task,
    progress_current: int,
    status_message: str | None,
    details_str: str,
    percent_override: int | None,
    logger: StandardLogger,
) -> None:
    await emit_task_progress_event(
        registry,
        task=task,
        task_id=task.task_id,
        progress_current=progress_current,
        status_message=status_message,
        details_str=details_str,
        percent_override=percent_override,
        logger=logger,
    )
