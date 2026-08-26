"""SoAI - Task runner for backup creation [backend/app/backup/task_create.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.backup_failure_notifications import (
    notify_backup_failure_noncritical,
    notify_backup_low_disk_noncritical,
)
from app.backup.task_outcome_lifecycle import (
    complete_backup_task_failure,
    complete_backup_task_success,
    start_backup_task_lifecycle,
)
from app.backup.task_result_validation import require_backup_bool_field
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import InsufficientDiskSpaceError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.serialization.json import normalize_for_json
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from app.backup.internal_protocols import BackupServiceContext

__all__ = ("run_create_backup_task",)

LOGGER_NAME = "SoAI.app.backup.task_create"
OPERATION = "app.backup.task_create.run_create_backup_task"
OPERATION_PUBLISH = "app.backup.task_create.publish_event"


async def run_create_backup_task(
    context: BackupServiceContext,
    task_id: str,
    *,
    user_id: int,
    operation: str,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    registry = context.runtime_dependencies.task_registry
    event_bus = context.runtime_dependencies.event_bus
    operation_name = str(operation).strip() or "create_backup"
    alert_operation_label = (
        "Scheduled backup" if operation_name == "scheduled_backup" else "Backup creation"
    )
    try:
        await start_backup_task_lifecycle(
            event_bus=event_bus,
            registry=registry,
            log=logger,
            task_id=task_id,
            user_id=user_id,
            operation=OPERATION,
            status_message="Creating backup",
            event_message="Backup started",
            event_details=str(operation_name),
            publish_operation=OPERATION_PUBLISH,
            update_failure_message="Failed to update backup creation start progress.",
            publish_failure_message="Failed to publish backup creation progress event.",
            publish_failure_details={"task_id": task_id, "operation": operation_name},
        )
        backup_result = await context.create_backup(task_id=task_id)
        if not isinstance(backup_result, dict):
            raise ValidationError("Backup create result must be a dict.")
        result = coerce_json_dict(normalize_for_json(backup_result))
        if result is None:
            raise ValidationError("Backup create result must be JSON-compatible.")
        success = require_backup_bool_field(
            result,
            field_name="success",
            error_message="Backup create result success must be a bool.",
        )
        if not success:
            await complete_backup_task_failure(
                log=logger,
                result=None,
                registry=registry,
                task_id=task_id,
                user_id=user_id,
                operation=OPERATION,
                event_bus=event_bus,
                error_code=500,
                error_message="Backup creation failed",
                publish_operation=OPERATION_PUBLISH,
                progress_message="Backup creation failed",
                progress_details=str(operation_name),
                finalize_failure_message="Failed to finalize backup creation task.",
                completion_fallback_failure_message="Failed to publish backup creation completion fallback event.",
                progress_failure_message="Failed to publish backup creation failure event.",
                publish_details={"task_id": task_id, "operation": operation_name},
            )
            await notify_backup_failure_noncritical(
                runtime_dependencies=context.runtime_dependencies,
                operation_label=alert_operation_label,
                task_id=task_id,
                log=logger,
            )
            return False
        backup_id = str(result.get("backup_id") or "")
        await complete_backup_task_success(
            log=logger,
            result=result,
            registry=registry,
            task_id=task_id,
            user_id=user_id,
            operation=OPERATION,
            event_bus=event_bus,
            publish_operation=OPERATION_PUBLISH,
            completion_message="Backup complete",
            progress_message="Backup complete",
            progress_details=backup_id,
            finalize_failure_message="Failed to finalize backup creation task.",
            completion_fallback_failure_message="Failed to publish backup creation completion fallback event.",
            progress_failure_message="Failed to publish backup completion event.",
            publish_details={"task_id": task_id, "backup_id": backup_id},
        )
        return True
    except InsufficientDiskSpaceError as exception:
        error_message = str(exception)
        log_handled_exception(
            logger,
            exception,
            message=error_message,
            operation=OPERATION,
            details={"task_id": task_id, **dict(exception.details or {})},
            level="warning",
        )
        await complete_backup_task_failure(
            log=logger,
            result=None,
            registry=registry,
            task_id=task_id,
            user_id=user_id,
            operation=OPERATION,
            event_bus=event_bus,
            error_code=507,
            error_message=error_message,
            publish_operation=OPERATION_PUBLISH,
            progress_message="Insufficient disk space",
            progress_details=error_message,
            finalize_failure_message="Failed to finalize backup creation task.",
            completion_fallback_failure_message="Failed to publish backup creation completion fallback event.",
            progress_failure_message="Failed to publish insufficient disk space event.",
            publish_details={"task_id": task_id},
        )
        await notify_backup_low_disk_noncritical(
            runtime_dependencies=context.runtime_dependencies,
            exception=exception,
            fallback_operation_label=alert_operation_label,
            task_id=task_id,
            log=logger,
        )
        await notify_backup_failure_noncritical(
            runtime_dependencies=context.runtime_dependencies,
            operation_label=alert_operation_label,
            task_id=task_id,
            log=logger,
        )
        return False
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Backup creation task failed.",
            operation=OPERATION,
            details={
                "task_id": task_id,
                "operation": operation_name,
                "task_type": "create",
            },
            level="warning",
        )
        await complete_backup_task_failure(
            log=logger,
            result=None,
            registry=registry,
            task_id=task_id,
            user_id=user_id,
            operation=OPERATION,
            event_bus=event_bus,
            error_code=500,
            error_message=str(exception),
            publish_operation=OPERATION_PUBLISH,
            progress_message="Backup failed",
            progress_details=str(exception),
            finalize_failure_message="Failed to finalize backup creation task.",
            completion_fallback_failure_message="Failed to publish backup creation completion fallback event.",
            progress_failure_message="Failed to publish backup failure event.",
            publish_details={"task_id": task_id, "operation": operation_name},
        )
        await notify_backup_failure_noncritical(
            runtime_dependencies=context.runtime_dependencies,
            operation_label=alert_operation_label,
            task_id=task_id,
            log=logger,
        )
        return False
