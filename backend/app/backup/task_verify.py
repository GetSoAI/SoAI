"""SoAI - Task runner for backup verification [backend/app/backup/task_verify.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.backup_verification import verify_backup
from app.backup.task_boolean_outcome_runner import (
    BooleanOutcomeTaskProfile,
    run_boolean_outcome_backup_task,
)
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from app.backup.internal_protocols import BackupServiceContext
    from core.types.json import JSONDict

__all__ = ("run_verify_backup_task",)

LOGGER_NAME = "SoAI.app.backup.task_verify"


async def _run_verify_backup(
    context: BackupServiceContext,
    backup_id: str,
    *,
    task_id: str,
    user_id: int,
) -> JSONDict:
    return await verify_backup(
        context,
        backup_id,
        task_id=task_id,
        user_id=user_id,
    )


async def run_verify_backup_task(
    context: BackupServiceContext,
    task_id: str,
    backup_id: str,
    *,
    user_id: int,
) -> None:
    profile = BooleanOutcomeTaskProfile(
        operation="app.backup.task_verify.run_verify_backup_task",
        publish_operation="app.backup.task_verify.publish_event",
        status_message="Verifying backup",
        start_event_message="Backup verification started",
        start_publish_failure_message="Failed to publish backup verification start event.",
        finalize_failure_message="Failed to finalize backup verification task.",
        success_completion_message="Backup verified",
        success_progress_message="Backup verified",
        success_progress_failure_message="Failed to publish backup verification completion event.",
        failure_error_message="Backup verification failed",
        failure_progress_message="Backup verification failed",
        failure_progress_failure_message="Failed to publish backup verification failure event.",
        exception_log_message="Backup verification task failed.",
        exception_progress_message_prefix="Backup verification failed",
        exception_progress_failure_message="Failed to publish backup verification exception event.",
        completion_fallback_failure_message="Failed to publish backup verification completion fallback event.",
        task_type="verify",
        alert_operation_label="Backup verification",
    )

    async def task_action(target_backup_id: str) -> JSONDict:
        return await _run_verify_backup(
            context,
            target_backup_id,
            task_id=task_id,
            user_id=user_id,
        )

    await run_boolean_outcome_backup_task(
        log=get_logger(LOGGER_NAME),
        task_target_id=backup_id,
        context=context,
        user_id=user_id,
        task_id=task_id,
        task_target_label="backup_id",
        result_field_name="success",
        task_action=task_action,
        profile=profile,
    )
