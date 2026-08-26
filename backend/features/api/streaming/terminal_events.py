"""SoAI - Task stream terminal event detection [backend/features/api/streaming/terminal_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_models_streaming import InferenceResultEvent, StreamEndEvent
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent, TaskStatusChangedEvent
from core.tasks.enums import TaskStatus

__all__ = (
    "build_eviction_terminal_event",
    "is_terminal_task_stream_event",
)


def build_eviction_terminal_event(task_id: str) -> TaskCompleteEvent:
    return TaskCompleteEvent(
        success=False,
        message="Task is no longer available in the registry.",
        task_id=task_id,
        status=TaskStatus.FAILED.value,
        error_code=404,
        error_message="Task is no longer available in the registry.",
    )


def is_terminal_task_stream_event(event: Event) -> bool:
    if isinstance(
        event,
        TaskCompleteEvent | ErrorEvent | InferenceResultEvent | StreamEndEvent,
    ):
        return True
    if isinstance(event, TaskStatusChangedEvent):
        try:
            new_status = event.new_status
        except AttributeError:
            new_status = None
        if isinstance(new_status, TaskStatus):
            return new_status.is_terminal()
        status_str = str(new_status or "").strip()
        if not status_str:
            return False
        try:
            return TaskStatus(status_str).is_terminal()
        except ValueError as exception:
            raise ValidationError(
                f"Invalid task status value: '{status_str}' is not a valid TaskStatus enum member.",
                operation="api_streaming.is_terminal_event",
                details={"status_str": status_str, "event_type": type(event).__name__},
                cause=exception,
            ) from exception
    return False
