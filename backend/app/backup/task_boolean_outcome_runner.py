"""SoAI - Shared backup task runner for boolean-result operations [backend/app/backup/task_boolean_outcome_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.backup_failure_notifications import notify_backup_failure_noncritical
from app.backup.task_outcome_lifecycle import (
    complete_backup_task_failure,
    complete_backup_task_success,
    start_backup_task_lifecycle,
)
from app.backup.task_result_validation import require_backup_bool_field
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from app.backup.internal_protocols import BackupServiceContext
    from core.types.json import JSONDict

__all__ = (
    "BooleanOutcomeTaskProfile",
    "run_boolean_outcome_backup_task",
)

OPERATION_BOOLEAN_OUTCOME_EXCEPTION = "app.backup.task_boolean_outcome_runner.run_task"


@dataclass(frozen=True, slots=True)
class BooleanOutcomeTaskProfile:
    operation: str
    publish_operation: str
    status_message: str
    start_event_message: str
    start_publish_failure_message: str
    finalize_failure_message: str
    success_completion_message: str
    success_progress_message: str
    success_progress_failure_message: str
    failure_error_message: str
    failure_progress_message: str
    failure_progress_failure_message: str
    exception_log_message: str
    exception_progress_message_prefix: str
    exception_progress_failure_message: str
    completion_fallback_failure_message: str
    task_type: str
    alert_operation_label: str


async def run_boolean_outcome_backup_task(
    *,
    context: BackupServiceContext,
    task_id: str,
    user_id: int,
    task_target_id: str,
    task_target_label: str,
    task_action: Callable[[str], Awaitable[JSONDict]],
    result_field_name: str,
    log: LoggerProtocol,
    profile: BooleanOutcomeTaskProfile,
) -> None:
    registry = context.runtime_dependencies.task_registry
    event_bus = context.runtime_dependencies.event_bus
    publish_details = {"task_id": task_id, task_target_label: str(task_target_id)}
    try:
        await start_backup_task_lifecycle(
            registry=registry,
            event_bus=event_bus,
            task_id=task_id,
            user_id=user_id,
            log=log,
            operation=profile.operation,
            publish_operation=profile.publish_operation,
            status_message=profile.status_message,
            event_message=profile.start_event_message,
            event_details=str(task_target_id),
            update_failure_message=f"Failed to update {profile.task_type} start progress.",
            publish_failure_message=profile.start_publish_failure_message,
            publish_failure_details=publish_details,
        )
        result = await task_action(task_target_id)
        if not isinstance(result, dict):
            raise ValidationError(f"{profile.task_type} result must be a dict.")
        if require_backup_bool_field(
            result,
            field_name=result_field_name,
            error_message=f"{profile.task_type} result {result_field_name} must be a bool.",
        ):
            await complete_backup_task_success(
                registry=registry,
                event_bus=event_bus,
                task_id=task_id,
                user_id=user_id,
                result=result,
                log=log,
                operation=profile.operation,
                publish_operation=profile.publish_operation,
                completion_message=profile.success_completion_message,
                progress_message=profile.success_progress_message,
                progress_details=str(task_target_id),
                finalize_failure_message=profile.finalize_failure_message,
                completion_fallback_failure_message=profile.completion_fallback_failure_message,
                progress_failure_message=profile.success_progress_failure_message,
                publish_details=publish_details,
            )
            return
        await complete_backup_task_failure(
            registry=registry,
            event_bus=event_bus,
            task_id=task_id,
            user_id=user_id,
            result=result,
            error_code=500,
            error_message=profile.failure_error_message,
            log=log,
            operation=profile.operation,
            publish_operation=profile.publish_operation,
            progress_message=profile.failure_progress_message,
            progress_details=str(task_target_id),
            finalize_failure_message=profile.finalize_failure_message,
            completion_fallback_failure_message=profile.completion_fallback_failure_message,
            progress_failure_message=profile.failure_progress_failure_message,
            publish_details=publish_details,
        )
        await notify_backup_failure_noncritical(
            runtime_dependencies=context.runtime_dependencies,
            operation_label=profile.alert_operation_label,
            task_id=task_id,
            log=log,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            log,
            exception,
            message=profile.exception_log_message,
            operation=OPERATION_BOOLEAN_OUTCOME_EXCEPTION,
            details={
                task_target_label: task_target_id,
                "task_id": task_id,
                "task_type": profile.task_type,
            },
            level="warning",
        )
        await complete_backup_task_failure(
            registry=registry,
            event_bus=event_bus,
            task_id=task_id,
            user_id=user_id,
            result=None,
            error_code=500,
            error_message=str(exception),
            log=log,
            operation=profile.operation,
            publish_operation=profile.publish_operation,
            progress_message=f"{profile.exception_progress_message_prefix}: {exception}",
            progress_details=str(task_target_id),
            finalize_failure_message=profile.finalize_failure_message,
            completion_fallback_failure_message=profile.completion_fallback_failure_message,
            progress_failure_message=profile.exception_progress_failure_message,
            publish_details=publish_details,
        )
        await notify_backup_failure_noncritical(
            runtime_dependencies=context.runtime_dependencies,
            operation_label=profile.alert_operation_label,
            task_id=task_id,
            log=log,
        )
