"""SoAI - Task registry notifications [backend/core/tasks/notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.events.types_tasks import TaskStatusChangedEvent
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from core.tasks.task_public_fields import resolve_public_task_terminal_fields

__all__ = (
    "notify_status_changed",
    "publish_event",
)

LOGGER_NAME = "SoAI.core.tasks.notifications"
OPERATION = "task_registry.publish_event"


async def publish_event(event_bus: EventBusProtocol, event: Event, name: str) -> None:
    logger = get_logger(LOGGER_NAME)
    if event_bus is None:
        return
    try:
        await event_bus.publish(event)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message=f"Failed to publish {name}.",
            operation=OPERATION,
            details={"event_name": name},
        )


async def notify_status_changed(
    event_bus: EventBusProtocol,
    task: Task,
    old_status: TaskStatus | None,
) -> None:
    try:
        current_status = task.status
    except AttributeError:
        return
    if old_status is not None and old_status != current_status:
        public_terminal_fields = resolve_public_task_terminal_fields(
            status=task.status,
            error_code=task.error_code,
            error_type=task.error_type,
            status_message=task.status_message,
            error_message=task.error_message,
        )
        await publish_event(
            event_bus,
            TaskStatusChangedEvent(
                task_id=task.task_id,
                old_status=old_status.value,
                new_status=current_status.value,
                owner_id=task.owner_id,
                user_id=task.user_id,
                status_message=public_terminal_fields.status_message,
            ),
            "TaskStatusChangedEvent",
        )
