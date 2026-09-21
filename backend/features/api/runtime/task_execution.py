"""SoAI - Task execution and finalization helpers for API routes [backend/features/api/runtime/task_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.noncritical_finalization import finalize_noncritical
from core.tasks.task_cancellation import cancel

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.types.json import JSONValue

__all__ = (
    "cancel_task_after_disconnect_safely",
    "cancel_task_safely",
    "finalize_task_safely",
)

OPERATION_FEATURES_API_RUNTIME_TASK_EXECUTION_CANCEL_TASK_SAFELY = (
    "features.api.runtime.task_execution.cancel_task_safely"
)
OPERATION_FEATURES_API_RUNTIME_TASK_EXECUTION_FINALIZE_TASK_SAFELY = (
    "features.api.runtime.task_execution.finalize_task_safely"
)

LOGGER_NAME = "SoAI.features.api.task_execution"


async def finalize_task_safely(
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    status: TaskStatus,
    operation: str,
    trace_id: str | None,
    result: dict[str, JSONValue] | None = None,
    error_code: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    status_message: str | None = None,
    details: dict[str, JSONValue] | None = None,
) -> None:
    resolved_details: dict[str, JSONValue] = {"task_id": task_id, "target_status": status.value}
    if details:
        resolved_details.update(details)
    resolved_details["operation"] = operation
    if trace_id is not None:
        resolved_details["trace_id"] = trace_id
    log_message = "Failed to finalize task (non-critical)."
    if status == TaskStatus.COMPLETED:
        log_message = "Failed to finalize task as completed (non-critical)."
    elif status == TaskStatus.FAILED:
        log_message = "Failed to finalize task as failed (non-critical)."
    elif status == TaskStatus.CANCELLED:
        log_message = "Failed to finalize task as cancelled (non-critical)."
    await finalize_noncritical(
        registry=registry,
        task_id=task_id,
        status=status,
        result=result,
        error_code=error_code,
        error_type=error_type,
        error_message=error_message,
        status_message=status_message,
        logger=get_logger(LOGGER_NAME),
        operation=OPERATION_FEATURES_API_RUNTIME_TASK_EXECUTION_FINALIZE_TASK_SAFELY,
        log_message=log_message,
        details=resolved_details,
    )


async def cancel_task_safely(
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    reason: str,
    operation: str,
    trace_id: str | None,
    details: dict[str, JSONValue] | None = None,
) -> None:
    normalized_reason = str(reason or "").strip() or "Cancelled by user"
    try:
        await cancel(registry, task_id, reason=normalized_reason)
    except RECOVERABLE_EXCEPTIONS as exception:
        resolved_details: dict[str, JSONValue] = {"task_id": task_id}
        if details:
            resolved_details.update(details)
        resolved_details["operation"] = operation
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to cancel task (non-critical).",
            operation=OPERATION_FEATURES_API_RUNTIME_TASK_EXECUTION_CANCEL_TASK_SAFELY,
            trace_id=trace_id,
            details=resolved_details,
            level="debug",
        )


async def cancel_task_after_disconnect_safely(
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    operation: str,
    trace_id: str | None,
    details: dict[str, JSONValue] | None = None,
) -> None:
    await cancel_task_safely(
        registry=registry,
        task_id=task_id,
        reason="Client disconnected.",
        operation=operation,
        trace_id=trace_id,
        details=details,
    )
