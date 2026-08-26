"""SoAI - Backup task registry progress, status, and finalization reporting [backend/app/backup/task_registry_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING

from app.backup.task_noncritical_execution import execute_noncritical_task_operation
from core.tasks.finalization import finalize
from core.tasks.status_transitions import update_progress, update_status

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.logging.protocols import LoggerProtocol
    from core.tasks.enums import TaskStatus
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.types.json import JSONValue

__all__ = (
    "finalize_task_noncritical",
    "update_progress_noncritical",
    "update_status_noncritical",
)


async def _execute_registry_operation[ResultT](
    *,
    operation_action: Awaitable[ResultT],
    log: LoggerProtocol,
    operation: str,
    message: str,
    task_id: str,
    level: str,
) -> ResultT | None:
    return await execute_noncritical_task_operation(
        operation_action=operation_action,
        log=log,
        operation=operation,
        message=message,
        task_id=task_id,
        level=level,
    )


async def finalize_task_noncritical(
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    status: TaskStatus,
    log: LoggerProtocol,
    operation: str,
    message: str,
    result: Mapping[str, JSONValue] | None = None,
    error_code: int | None = None,
    error_message: str | None = None,
    level: str = "warning",
) -> bool:
    task = await _execute_registry_operation(
        operation_action=finalize(
            registry,
            task_id,
            status,
            result=result,
            error_code=error_code,
            error_message=error_message,
        ),
        log=log,
        operation=operation,
        message=message,
        task_id=task_id,
        level=level,
    )
    return task is not None


async def update_progress_noncritical(
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    progress_current: int,
    log: LoggerProtocol,
    operation: str,
    message: str,
    status_message: str | None = None,
    details: JSONValue | None = None,
    percent_override: int | None = None,
    level: str = "warning",
) -> None:
    await _execute_registry_operation(
        operation_action=update_progress(
            registry,
            task_id,
            progress_current,
            status_message=status_message,
            details=details,
            percent_override=percent_override,
        ),
        log=log,
        operation=operation,
        message=message,
        task_id=task_id,
        level=level,
    )


async def update_status_noncritical(
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    new_status: TaskStatus,
    log: LoggerProtocol,
    operation: str,
    message: str,
    status_message: str | None = None,
    level: str = "warning",
) -> None:
    await _execute_registry_operation(
        operation_action=update_status(
            registry,
            task_id,
            new_status,
            status_message=status_message,
        ),
        log=log,
        operation=operation,
        message=message,
        task_id=task_id,
        level=level,
    )
