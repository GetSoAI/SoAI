"""SoAI - Task runner for backup deletion [backend/app/backup/task_delete.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.task_boolean_outcome_runner import (
    BooleanOutcomeTaskProfile,
    run_boolean_outcome_backup_task,
)
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from app.backup.internal_protocols import BackupServiceContext

__all__ = ("run_delete_backup_task",)

LOGGER_NAME = "SoAI.app.backup.task_delete"


async def run_delete_backup_task(
    context: BackupServiceContext,
    task_id: str,
    backup_id: str,
    *,
    user_id: int,
) -> None:
    profile = BooleanOutcomeTaskProfile(
        operation="app.backup.task_delete.run_delete_backup_task",
        publish_operation="app.backup.task_delete.publish_event",
        status_message="Deleting backup",
        start_event_message="Backup deletion started",
        start_publish_failure_message="Failed to publish backup deletion start event.",
        finalize_failure_message="Failed to finalize backup deletion task.",
        success_completion_message="Backup deleted",
        success_progress_message="Backup deleted",
        success_progress_failure_message="Failed to publish backup deletion completion event.",
        failure_error_message="Backup deletion failed",
        failure_progress_message="Backup deletion failed",
        failure_progress_failure_message="Failed to publish backup deletion failure event.",
        exception_log_message="Backup deletion task failed.",
        exception_progress_message_prefix="Backup deletion failed",
        exception_progress_failure_message="Failed to publish backup deletion exception event.",
        completion_fallback_failure_message="Failed to publish backup deletion completion fallback event.",
        task_type="delete",
        alert_operation_label="Backup deletion",
    )
    await run_boolean_outcome_backup_task(
        context=context,
        task_id=task_id,
        task_target_id=backup_id,
        user_id=user_id,
        task_target_label="backup_id",
        log=get_logger(LOGGER_NAME),
        result_field_name="deleted",
        task_action=context.delete_backup,
        profile=profile,
    )
