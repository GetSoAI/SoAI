"""SoAI - Restore task failure classification and recovery [backend/app/backup/restore_task_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.backup_failure_notifications import (
    notify_backup_failure_noncritical,
    notify_backup_low_disk_noncritical,
)
from app.backup.restore_task_recovery import handle_restore_failure
from app.backup.task_event_publishing import (
    publish_failed_task_complete_event_noncritical,
)
from app.backup.task_registry_reporting import finalize_task_noncritical
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    NotFoundError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus

if TYPE_CHECKING:
    from app.backup.internal_protocols import RestoreTaskRunnerContext
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = ("handle_restore_task_exception",)

LOGGER_NAME = "SoAI.app.backup.restore_task_failures"


async def handle_restore_task_exception(
    *,
    context: RestoreTaskRunnerContext,
    task_id: str,
    backup_id: str,
    user_id: int,
    registry: TaskRegistryProtocol,
    project_root: str,
    maintenance_transition_started: bool,
    restore_destinations: dict[str, str] | None,
    restore_results: list[JSONDict],
    database_core_shutdown: bool,
    exception: Exception,
) -> None:
    logger = get_logger(LOGGER_NAME)
    error_code = 500
    restart_reason = "backup_restore_exception"
    error_message = str(exception)

    if isinstance(exception, InsufficientDiskSpaceError):
        error_code = 507
        error_message = exception.message
        restart_reason = "backup_restore_insufficient_disk_after_maintenance"
    elif isinstance(exception, NotFoundError):
        error_code = 404
        error_message = exception.message
        restart_reason = "backup_restore_not_found_after_maintenance"
    elif isinstance(exception, ValidationError | SecurityError):
        error_code = 400
        error_message = exception.message
        restart_reason = "backup_restore_invalid_after_maintenance"
    elif isinstance(exception, StateError):
        error_message = exception.message
        restart_reason = "backup_restore_state_error_after_maintenance"
    elif not isinstance(exception, RECOVERABLE_EXCEPTIONS):
        raise TypeError("exception must be a handled restore task exception.")

    if not maintenance_transition_started:
        finalized = await finalize_task_noncritical(
            registry=registry,
            task_id=task_id,
            status=TaskStatus.FAILED,
            log=logger,
            operation="app.backup.restore_task_failures.finalize",
            message="Failed to finalize restore task before maintenance transition.",
            error_code=error_code,
            error_message=error_message,
        )
        if not finalized:
            await publish_failed_task_complete_event_noncritical(
                event_bus=context.runtime_dependencies.event_bus,
                task_id=str(task_id),
                user_id=int(user_id),
                error_code=error_code,
                error_message=error_message,
                log=logger,
                operation="app.backup.restore_task_failures.publish",
                message="Failed to publish restore failure completion fallback event.",
                details={"task_id": str(task_id), "backup_id": str(backup_id)},
            )
        if isinstance(exception, InsufficientDiskSpaceError):
            await notify_backup_low_disk_noncritical(
                runtime_dependencies=context.runtime_dependencies,
                exception=exception,
                fallback_operation_label="Backup restore",
                task_id=task_id,
                log=logger,
            )
        await notify_backup_failure_noncritical(
            runtime_dependencies=context.runtime_dependencies,
            operation_label="Backup restore",
            task_id=task_id,
            log=logger,
        )
        return

    failure_db_path = None
    if database_core_shutdown and restore_destinations is not None:
        failure_db_path = restore_destinations.get("db_path")
    await handle_restore_failure(
        context,
        user_id=user_id,
        task_id=task_id,
        registry=registry,
        backup_id=backup_id,
        project_root=project_root,
        error_message=error_message,
        error_code=error_code,
        restart_reason=restart_reason,
        finalize_restored_db=database_core_shutdown,
        restore_results=restore_results,
        restore_destinations=restore_destinations,
        db_path=failure_db_path,
        exception=exception,
    )
