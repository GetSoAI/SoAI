"""SoAI - Restore phase rollback transition handling [backend/app/backup/restore_phase_rollback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.restore_task_recovery import handle_restore_failure
from app.backup.restore_task_rollback import attempt_restore_rollback_from_journal
from app.backup.task_registry_reporting import update_progress_noncritical
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from app.backup.internal_protocols import RestoreTaskRunnerContext
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = ("handle_cancelled_phase_rollback", "handle_phase_rollback")

LOGGER_NAME = "SoAI.app.backup.restore_phase_rollback"
OPERATION = "app.backup.restore_phase_rollback.handle"


async def handle_cancelled_phase_rollback(
    *,
    context: RestoreTaskRunnerContext,
    project_root: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    rollback_result = await attempt_restore_rollback_from_journal(
        project_root=project_root,
        logger=logger,
    )
    restart_reason = (
        "backup_restore_cancelled_recovery_pending"
        if rollback_result == "recovery_pending"
        else "backup_restore_cancelled"
    )
    context.runtime_dependencies.request_restart(restart_reason)


async def handle_phase_rollback(
    *,
    context: RestoreTaskRunnerContext,
    project_root: str,
    restore_results: list[JSONDict],
    restore_destinations: dict[str, str],
    finalize_restored_db: bool,
    backup_id: str,
    task_id: str,
    user_id: int,
    registry: TaskRegistryProtocol,
    progress_percent: int,
    error_message: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    await update_progress_noncritical(
        registry=registry,
        task_id=task_id,
        progress_current=progress_percent,
        log=logger,
        operation=OPERATION,
        message="Failed to update restore rollback progress.",
        status_message="Rolling back from snapshot due to restore errors",
        level="debug",
    )
    rollback_db_path = restore_destinations.get("db_path") if finalize_restored_db else None
    rollback_restart_reason = "backup_restore_rolled_back"
    await handle_restore_failure(
        context,
        registry=registry,
        user_id=user_id,
        task_id=task_id,
        backup_id=backup_id,
        project_root=project_root,
        error_message=error_message,
        error_code=500,
        restart_reason=rollback_restart_reason,
        restore_results=restore_results,
        finalize_restored_db=finalize_restored_db,
        restore_destinations=restore_destinations,
        db_path=rollback_db_path,
    )
