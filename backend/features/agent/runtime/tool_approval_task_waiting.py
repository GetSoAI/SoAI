"""SoAI - Agent tool approval task waiting [backend/features/agent/runtime/tool_approval_task_waiting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError, StateError
from core.notifications.notification_deletion import (
    delete_metadata_notification_noncritical,
)
from core.tasks.enums import TaskStatus
from core.tasks.noncritical_finalization import finalize_noncritical
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.tasks.protocols import CancellationHistoryProtocol
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONValue

__all__ = (
    "ToolApprovalWaitOutcome",
    "delete_tool_approval_notification_noncritical",
    "wait_for_tool_approval_completion",
)

OPERATION_TASK_MISSING = "agent.tool_approval_tasks.task_missing"
OPERATION_NOTIFICATION_DELETE_FAILED = "agent.tool_approval_tasks.notification_delete_failed"


@dataclass(frozen=True, slots=True)
class ToolApprovalWaitOutcome:
    task: Task | None
    was_cancelled: bool


async def delete_tool_approval_notification_noncritical(
    *,
    logger: LoggerProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    metadata: Mapping[str, JSONValue],
    conv_id: str,
    task_id: str,
    notification_id: str,
) -> None:
    await delete_metadata_notification_noncritical(
        logger=logger,
        database_notifications=database_notifications,
        user_id=int(user_id),
        metadata=metadata,
        operation=OPERATION_NOTIFICATION_DELETE_FAILED,
        message="Failed to delete tool approval notification (non-critical).",
        level="warning",
        details={
            "user_id": int(user_id),
            "conv_id": conv_id,
            "task_id": task_id,
            "notification_id": notification_id,
        },
    )


async def wait_for_tool_approval_completion(
    *,
    task_registry: TaskRegistryProtocol,
    cancellation_history: CancellationHistoryProtocol | None,
    task_cancellation_id: str,
    task_id: str,
    expires_at_ms: int | None,
    logger: LoggerProtocol,
    details: Mapping[str, JSONValue],
) -> ToolApprovalWaitOutcome:
    if expires_at_ms is None or expires_at_ms <= 0:
        raise StateError("Tool approval timeout must be positive.")
    completed: Task | None = None
    while True:
        if cancellation_history is not None and await cancellation_history.is_cancelled(
            task_cancellation_id,
        ):
            return ToolApprovalWaitOutcome(task=None, was_cancelled=True)
        remaining_ms = int(expires_at_ms) - epoch_ms()
        if remaining_ms <= 0:
            await finalize_noncritical(
                task_registry,
                task_id,
                TaskStatus.FAILED,
                error_code=504,
                error_message="Timed out waiting for user approval.",
                status_message="Timed out",
                logger=logger,
                operation="agent.tool_approval_tasks.timeout.finalize",
                log_message="Failed to finalize expired tool approval task (non-critical).",
                details=dict(details),
            )
            completed = await task_registry.get(task_id, force_refresh=True)
            break
        try:
            completed = await task_registry.wait_for_completion(
                task_id,
                timeout=min(1.0, float(remaining_ms) / 1000.0),
            )
        except SoAITimeoutError:
            continue
        break
    if completed is None:
        log_exception(
            logger,
            StateError(
                "Tool approval task disappeared while waiting; rejecting tool call.",
                operation=OPERATION_TASK_MISSING,
            ),
            message="Tool approval task not found; rejecting tool call.",
            operation=OPERATION_TASK_MISSING,
            level="warning",
            details=dict(details),
        )
        return ToolApprovalWaitOutcome(task=None, was_cancelled=False)
    if completed.status.is_terminal():
        return ToolApprovalWaitOutcome(task=completed, was_cancelled=False)
    return ToolApprovalWaitOutcome(task=None, was_cancelled=False)
