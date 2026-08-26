"""SoAI - Backup task lifecycle event and finalization flow [backend/app/backup/task_outcome_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.task_event_publishing import (
    publish_event_noncritical,
    publish_failed_task_complete_event_noncritical,
)
from app.backup.task_registry_reporting import (
    finalize_task_noncritical,
    update_progress_noncritical,
)
from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.tasks.enums import TaskStatus

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.types.json import JSONDict

__all__ = (
    "complete_backup_task_failure",
    "complete_backup_task_success",
    "start_backup_task_lifecycle",
)


async def start_backup_task_lifecycle(
    *,
    registry: TaskRegistryLifecycleView,
    event_bus: EventBusProtocol,
    task_id: str,
    user_id: int,
    log: LoggerProtocol,
    operation: str,
    publish_operation: str,
    status_message: str,
    event_message: str,
    event_details: str,
    update_failure_message: str,
    publish_failure_message: str,
    publish_failure_details: dict[str, str],
) -> None:
    await update_progress_noncritical(
        registry=registry,
        task_id=task_id,
        progress_current=0,
        log=log,
        operation=operation,
        message=update_failure_message,
        status_message=status_message,
        level="debug",
    )
    await publish_event_noncritical(
        event_bus=event_bus,
        event=TaskProgressEvent(
            percent=0,
            message=event_message,
            details=event_details,
            task_id=str(task_id),
            user_id=int(user_id),
        ),
        log=log,
        operation=publish_operation,
        message=publish_failure_message,
        details=publish_failure_details,
    )


async def complete_backup_task_success(
    *,
    registry: TaskRegistryLifecycleView,
    event_bus: EventBusProtocol,
    task_id: str,
    user_id: int,
    result: JSONDict,
    log: LoggerProtocol,
    operation: str,
    publish_operation: str,
    completion_message: str,
    progress_message: str,
    progress_details: str,
    finalize_failure_message: str,
    completion_fallback_failure_message: str,
    progress_failure_message: str,
    publish_details: dict[str, str],
) -> None:
    finalized = await finalize_task_noncritical(
        registry=registry,
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        result=result,
        log=log,
        operation=operation,
        message=finalize_failure_message,
    )
    if not finalized:
        await publish_event_noncritical(
            event_bus=event_bus,
            event=TaskCompleteEvent(
                success=True,
                message=completion_message,
                task_id=str(task_id),
                user_id=int(user_id),
                status=TaskStatus.COMPLETED.value,
            ),
            log=log,
            operation=publish_operation,
            message=completion_fallback_failure_message,
            details=publish_details,
        )
    await publish_event_noncritical(
        event_bus=event_bus,
        event=TaskProgressEvent(
            percent=100,
            message=progress_message,
            details=progress_details,
            task_id=str(task_id),
            user_id=int(user_id),
        ),
        log=log,
        operation=publish_operation,
        message=progress_failure_message,
        details=publish_details,
    )


async def complete_backup_task_failure(
    *,
    registry: TaskRegistryLifecycleView,
    event_bus: EventBusProtocol,
    task_id: str,
    user_id: int,
    result: JSONDict | None,
    error_code: int,
    error_message: str,
    log: LoggerProtocol,
    operation: str,
    publish_operation: str,
    progress_message: str,
    progress_details: str,
    finalize_failure_message: str,
    completion_fallback_failure_message: str,
    progress_failure_message: str,
    publish_details: dict[str, str],
) -> None:
    finalized = await finalize_task_noncritical(
        registry=registry,
        task_id=task_id,
        status=TaskStatus.FAILED,
        result=result,
        log=log,
        operation=operation,
        message=finalize_failure_message,
        error_code=error_code,
        error_message=error_message,
    )
    if not finalized:
        await publish_failed_task_complete_event_noncritical(
            event_bus=event_bus,
            task_id=str(task_id),
            user_id=int(user_id),
            error_code=error_code,
            error_message=error_message,
            log=log,
            operation=publish_operation,
            message=completion_fallback_failure_message,
            details=publish_details,
        )
    await publish_event_noncritical(
        event_bus=event_bus,
        event=TaskProgressEvent(
            percent=100,
            message=progress_message,
            details=progress_details,
            task_id=str(task_id),
            user_id=int(user_id),
        ),
        log=log,
        operation=publish_operation,
        message=progress_failure_message,
        details=publish_details,
    )
