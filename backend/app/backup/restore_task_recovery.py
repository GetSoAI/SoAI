"""SoAI - Backup restore rollback snapshot recovery and exception handling [backend/app/backup/restore_task_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from app.backup.backup_failure_notifications import (
    notify_backup_failure_noncritical,
    notify_backup_low_disk_noncritical,
)
from app.backup.internal_protocols import RestoreTaskRunnerContext
from app.backup.restore_task_rollback import attempt_restore_rollback_from_journal
from app.backup.task_registry_reporting import finalize_task_noncritical
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.sqlite.file_permissions import secure_sqlite_file_permissions
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol
from database.repositories.tasks.backup import sync_finalize_restored_backup_task

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("handle_restore_failure",)

OPERATION_APPLICATION_RESTORE_RECOVERY_FINALIZE_REGISTRY = (
    "application_restore.recovery.finalize_registry"
)
OPERATION_APPLICATION_RESTORE_RECOVERY_FINALIZE_RESTORED_DB = (
    "application_restore.recovery.finalize_restored_db"
)
LOGGER_NAME = "SoAI.app.backup.restore_task_recovery"


def _extract_restore_errors(restore_results: list[JSONDict] | None) -> list[JSONDict]:
    restore_errors: list[JSONDict] = []
    if not restore_results:
        return restore_errors
    for restore_item in restore_results:
        error_values = restore_item.get("errors")
        if isinstance(error_values, list):
            for error_value in error_values:
                if isinstance(error_value, dict):
                    restore_errors.append(dict(error_value))
    return restore_errors


async def handle_restore_failure(
    self: RestoreTaskRunnerContext,
    *,
    project_root: str,
    task_id: str,
    backup_id: str,
    user_id: int,
    registry: TaskRegistryProtocol,
    error_message: str,
    error_code: int = 500,
    restart_reason: str,
    restore_results: list[JSONDict] | None = None,
    restore_destinations: dict[str, str] | None = None,
    finalize_restored_db: bool = False,
    db_path: str | None = None,
    exception: Exception | None = None,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    rollback_result = await attempt_restore_rollback_from_journal(
        project_root=project_root,
        logger=logger,
    )
    recovery_pending = rollback_result in {"recovery_pending", "commit_recovery_pending"}
    if recovery_pending:
        error_message = "Restore failed; durable rollback will resume during startup"
        restart_reason = "backup_restore_recovery_pending"
    restore_errors = _extract_restore_errors(restore_results)
    if exception is not None:
        restore_errors.append({"error": project_public_exception(exception).message})
    combined_result: JSONDict = {
        "backup_id": backup_id,
        "files_restored": [],
        "errors": restore_errors,
        "success": False,
        "rolled_back": rollback_result == "rolled_back",
        "rollback_state": rollback_result,
    }
    if not finalize_restored_db:
        await finalize_task_noncritical(
            registry=registry,
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
            result=combined_result,
            log=logger,
            operation=OPERATION_APPLICATION_RESTORE_RECOVERY_FINALIZE_REGISTRY,
            message="Failed to finalize restore task via TaskRegistry",
        )
    resolved_db_path = db_path
    if (
        finalize_restored_db
        and resolved_db_path is None
        and restore_destinations
        and restore_destinations.get("db_path")
    ):
        resolved_db_path = str(restore_destinations["db_path"])
    if finalize_restored_db and resolved_db_path and not recovery_pending:
        try:
            await run_joined_thread_call(
                secure_sqlite_file_permissions,
                resolved_db_path,
                task_name="backup-restore-failure-database-permissions",
            )
            await run_joined_thread_call(
                partial(
                    sync_finalize_restored_backup_task,
                    db_path=resolved_db_path,
                    task_id=task_id,
                    user_id=int(user_id),
                    backup_id=backup_id,
                    result=combined_result,
                    success=False,
                ),
                task_name="backup-restore-failure-database-task-finalize",
            )
        except RECOVERABLE_EXCEPTIONS as finalize_restored_db_exception:
            log_exception(
                logger,
                finalize_restored_db_exception,
                message="Failed to finalize restore task in restored database",
                operation=OPERATION_APPLICATION_RESTORE_RECOVERY_FINALIZE_RESTORED_DB,
                level="warning",
            )
        await run_joined_thread_call(
            secure_sqlite_file_permissions,
            resolved_db_path,
            task_name="backup-restore-failure-database-permissions",
        )
    if not finalize_restored_db and isinstance(exception, InsufficientDiskSpaceError):
        await notify_backup_low_disk_noncritical(
            runtime_dependencies=self.runtime_dependencies,
            exception=exception,
            fallback_operation_label="Backup restore",
            task_id=task_id,
            log=logger,
        )
    if not finalize_restored_db:
        await notify_backup_failure_noncritical(
            runtime_dependencies=self.runtime_dependencies,
            operation_label="Backup restore",
            task_id=task_id,
            log=logger,
        )
    self.runtime_dependencies.request_restart(restart_reason)
    return combined_result
