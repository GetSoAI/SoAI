"""SoAI - Task polling decisions for stream event synthesis [backend/features/api/streaming/task_polling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.progress.percent import coerce_percent_or_default
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from core.tasks.task_public_fields import resolve_public_task_terminal_fields

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "TaskPollResult",
    "task_to_complete_event",
    "task_to_progress_event",
)


def task_to_progress_event(task: Task) -> TaskProgressEvent:
    percent_value = task.progress_percent()
    percent = coerce_percent_or_default(percent_value, default=0)
    return TaskProgressEvent(
        percent=percent,
        message=task.status_message or task.status.value,
        details=task.progress_details or "",
        task_id=task.task_id,
        user_id=task.user_id,
    )


def task_to_complete_event(task: Task) -> TaskCompleteEvent:
    public_fields = resolve_public_task_terminal_fields(task)
    message = public_fields.status_message or public_fields.error_message or task.status.value
    return TaskCompleteEvent(
        success=task.status == TaskStatus.COMPLETED,
        message=message,
        task_id=task.task_id,
        user_id=task.user_id,
        status=task.status.value,
        error_code=task.error_code,
        error_type=task.error_type,
        error_message=public_fields.error_message,
    )


@dataclass(slots=True)
class TaskPollResult:
    changed: bool
    fingerprint: tuple[JSONValue, ...]
    interval: float
    event: TaskProgressEvent | TaskCompleteEvent | None = None
    is_terminal: bool = False
