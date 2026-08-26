"""SoAI - Non-critical backup task event publication [backend/app/backup/task_event_publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.task_noncritical_execution import execute_noncritical_task_operation
from core.events.types_tasks import TaskCompleteEvent
from core.tasks.enums import TaskStatus

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "build_failed_task_complete_event",
    "publish_event_noncritical",
    "publish_failed_task_complete_event_noncritical",
)


def build_failed_task_complete_event(
    *,
    task_id: str,
    user_id: int,
    error_code: int,
    error_message: str,
) -> TaskCompleteEvent:
    return TaskCompleteEvent(
        success=False,
        message=error_message,
        task_id=task_id,
        user_id=user_id,
        status=TaskStatus.FAILED.value,
        error_code=error_code,
        error_message=error_message,
    )


async def publish_failed_task_complete_event_noncritical(
    *,
    event_bus: EventBusProtocol,
    task_id: str,
    user_id: int,
    error_code: int,
    error_message: str,
    log: LoggerProtocol,
    operation: str,
    message: str,
    details: dict[str, str],
) -> None:
    failed_event = build_failed_task_complete_event(
        task_id=task_id,
        user_id=user_id,
        error_code=error_code,
        error_message=error_message,
    )
    await publish_event_noncritical(
        event_bus=event_bus,
        event=failed_event,
        details=details,
        log=log,
        message=message,
        operation=operation,
    )


async def publish_event_noncritical(
    *,
    event_bus: EventBusProtocol,
    event: Event,
    log: LoggerProtocol,
    operation: str,
    message: str,
    details: dict[str, str],
    level: str = "warning",
) -> None:
    task_id = str(details["task_id"]) if "task_id" in details else ""
    await execute_noncritical_task_operation(
        log=log,
        message=message,
        operation=operation,
        operation_action=event_bus.publish(event),
        task_id=task_id,
        level=level,
    )
