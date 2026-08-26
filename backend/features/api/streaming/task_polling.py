"""SoAI - Task polling decisions for stream event synthesis [backend/features/api/streaming/task_polling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.progress.percent import coerce_percent_or_default
from core.tasks.enums import TaskStatus
from core.tasks.task import Task

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "TaskPollResult",
    "compute_task_poll_state",
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
    message = task.status_message or task.error_message or task.status.value
    return TaskCompleteEvent(
        success=task.status == TaskStatus.COMPLETED,
        message=message,
        task_id=task.task_id,
        user_id=task.user_id,
        status=task.status.value,
        error_code=task.error_code,
        error_type=task.error_type,
        error_message=task.error_message,
    )


@dataclass(slots=True)
class TaskPollResult:
    changed: bool
    fingerprint: tuple[JSONValue, ...]
    interval: float
    event: TaskProgressEvent | TaskCompleteEvent | None = None
    is_terminal: bool = False


def compute_task_poll_state(
    task: Task,
    last_fingerprint: tuple[JSONValue, ...] | None,
    *,
    default_interval: float = 1.0,
    min_interval: float = 0.5,
    max_interval: float = 2.0,
) -> TaskPollResult:
    fingerprint = (
        task.status.value,
        task.progress_current,
        task.progress_total,
        task.status_message,
        task.error_code,
        task.error_type,
        task.error_message,
        task.update_counter,
    )
    changed = fingerprint != last_fingerprint
    interval = default_interval
    try:
        try:
            configured_value = task.poll_interval_ms
        except AttributeError:
            configured_value = 0
        configured_ms = int(configured_value or 0)
        if configured_ms > 0:
            interval = configured_ms / 1000.0
    except (TypeError, ValueError):
        interval = default_interval
    interval = max(min_interval, min(max_interval, interval))
    is_terminal = task.status.is_terminal()
    event = None
    if changed:
        event = task_to_complete_event(task) if is_terminal else task_to_progress_event(task)
    return TaskPollResult(
        changed=changed,
        fingerprint=fingerprint,
        interval=interval,
        event=event,
        is_terminal=is_terminal,
    )
