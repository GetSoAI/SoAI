"""SoAI - Agent tool approval task lifecycle [backend/features/agent/runtime/tool_approval_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.interaction_checkpoint import (
    build_conversation_interaction_checkpoint,
    raise_if_conversation_input_suspended,
)
from core.elicitation_interactions import extract_notification_id
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.runtime.soai_identifiers import extend_soai_id
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.enums import TaskStatus
from core.tasks.noncritical_finalization import finalize_noncritical
from core.tool_approval.task_metadata import build_tool_approval_task_metadata
from features.agent.runtime.tool_approval_task_creation import (
    build_tool_approval_notification_id,
    build_tool_approval_task_id,
    ensure_tool_approval_task,
)
from features.agent.runtime.tool_approval_task_waiting import (
    delete_tool_approval_notification_noncritical,
    wait_for_tool_approval_completion,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import CancellationHistoryProtocol
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONValue

__all__ = (
    "ToolApprovalTaskOutcome",
    "await_tool_approval_outcome",
)

OPERATION_TASK_FAILED = "agent.tool_approval_tasks.task_failed"
OPERATION_TASK_MISSING = "agent.tool_approval_tasks.task_missing"
OPERATION_TASK_RESULT = "agent.tool_approval_tasks.task_result"
OPERATION_TASK_STATUS = "agent.tool_approval_tasks.task_status"
OPERATION_NOTIFICATION_ID_MISSING = "agent.tool_approval_tasks.notification_id_missing"


@dataclass(frozen=True, slots=True)
class ToolApprovalTaskOutcome:
    approved: bool | None
    remember: bool


def _coerce_bool_result(
    result: Mapping[str, JSONValue] | None,
    *,
    field: str,
) -> bool:
    if result is None:
        return False
    value = result.get(field)
    return value is True


def _decode_approval_task_result(
    logger: LoggerProtocol,
    *,
    task: Task,
    details: Mapping[str, JSONValue],
) -> ToolApprovalTaskOutcome:
    if task.status == TaskStatus.CANCELLED:
        return ToolApprovalTaskOutcome(approved=None, remember=False)
    if task.status == TaskStatus.FAILED:
        log_exception(
            logger,
            ValidationError(
                "Tool approval task ended in failed status; rejecting tool call.",
                operation=OPERATION_TASK_FAILED,
            ),
            message="Tool approval task failed; rejecting tool call.",
            operation=OPERATION_TASK_FAILED,
            level="warning",
            details=dict(details),
        )
        return ToolApprovalTaskOutcome(approved=False, remember=False)
    if task.status != TaskStatus.COMPLETED:
        log_exception(
            logger,
            ValidationError(
                f"Tool approval task ended with unexpected status: {task.status.value}",
                operation=OPERATION_TASK_STATUS,
            ),
            message="Tool approval task ended with unexpected status; rejecting tool call.",
            operation=OPERATION_TASK_STATUS,
            level="warning",
            details={**details, "status": task.status.value},
        )
        return ToolApprovalTaskOutcome(approved=False, remember=False)
    result_value = task.result
    result = result_value if isinstance(result_value, Mapping) else None
    approved = _coerce_bool_result(result, field="approved")
    remember = _coerce_bool_result(result, field="remember")
    if approved:
        return ToolApprovalTaskOutcome(approved=True, remember=remember)
    approved_value = result.get("approved") if result is not None else None
    if approved_value is False:
        return ToolApprovalTaskOutcome(approved=False, remember=False)
    log_exception(
        logger,
        ValidationError(
            "Tool approval task completed without a boolean approved flag; rejecting tool call.",
            operation=OPERATION_TASK_RESULT,
        ),
        message="Tool approval task result invalid; rejecting tool call.",
        operation=OPERATION_TASK_RESULT,
        level="warning",
        details={**details, "approved": approved_value},
    )
    return ToolApprovalTaskOutcome(approved=False, remember=False)


async def await_tool_approval_outcome(
    *,
    task_registry: TaskRegistryProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    conversation_attention: ConversationAttentionCoordinatorProtocol,
    cancellation_history: CancellationHistoryProtocol | None,
    cancellation_id: str,
    logger: LoggerProtocol,
    request_context: RequestContext,
    user_id: int,
    conv_id: str,
    turn_id: str,
    iteration_index: int,
    tool_call_id: str,
    tool_name: str,
    tool_key: str | None,
    tool_arguments: str | None,
    user_interaction_timeout_ms: int,
) -> ToolApprovalTaskOutcome:
    details: dict[str, JSONValue] = {
        "conv_id": conv_id,
        "user_id": int(user_id),
        "turn_id": turn_id,
        "iteration_index": int(iteration_index),
        "tool_call_id": tool_call_id,
    }
    task_id = build_tool_approval_task_id(
        conv_id=conv_id,
        turn_id=turn_id,
        iteration_index=iteration_index,
        tool_call_id=tool_call_id,
    )
    normalized_base_cancellation_id = normalize_cancellation_id(cancellation_id)
    if not normalized_base_cancellation_id:
        raise ValidationError("Tool approval requires a non-empty cancellation_id.")
    task_cancellation_id = extend_soai_id(
        normalized_base_cancellation_id,
        ("tool_approval", conv_id, turn_id, str(iteration_index), tool_call_id),
    )
    notification_id = build_tool_approval_notification_id(task_id=task_id)
    metadata = build_tool_approval_task_metadata(
        conv_id=conv_id,
        turn_id=turn_id,
        iteration_index=iteration_index,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_key=tool_key,
        tool_arguments=tool_arguments,
        notification_id=notification_id,
    )
    interaction_checkpoint = build_conversation_interaction_checkpoint(
        request_context,
        interaction_type="tool_approval",
        suspension_phase="before_approved_tool",
        conv_id=conv_id,
        iteration_index=iteration_index,
        turn_id=turn_id,
        tool_call_id=tool_call_id,
        tool_arguments=tool_arguments,
        user_interaction_timeout_ms=user_interaction_timeout_ms,
    )
    task = await ensure_tool_approval_task(
        task_registry,
        database_notifications,
        conversation_attention,
        logger,
        task_id=task_id,
        user_id=int(user_id),
        conv_id=conv_id,
        task_cancellation_id=task_cancellation_id,
        metadata=metadata,
        interaction_checkpoint=interaction_checkpoint,
        user_interaction_timeout_ms=user_interaction_timeout_ms,
    )
    await raise_if_conversation_input_suspended(
        task_registry,
        input_id=request_context.conversation_input_id,
        task_id=task.task_id,
    )
    resolved_notification_id = extract_notification_id(task.metadata)
    if resolved_notification_id is None:
        raise StateError(
            "Tool approval task notification_id metadata is missing.",
            operation=OPERATION_NOTIFICATION_ID_MISSING,
            details={**details, "task_id": task.task_id},
        )
    notification_id = resolved_notification_id
    if task.status.is_terminal():
        outcome = _decode_approval_task_result(
            logger,
            task=task,
            details={**details, "task_id": task.task_id},
        )
        await delete_tool_approval_notification_noncritical(
            logger=logger,
            database_notifications=database_notifications,
            user_id=user_id,
            metadata=task.metadata,
            conv_id=conv_id,
            task_id=task.task_id,
            notification_id=notification_id,
        )
        return outcome
    wait_outcome = await wait_for_tool_approval_completion(
        task_registry=task_registry,
        cancellation_history=cancellation_history,
        task_cancellation_id=task_cancellation_id,
        task_id=task.task_id,
        expires_at_ms=task.ttl_expires_at_ms,
        logger=logger,
        details={**details, "task_id": task.task_id},
    )
    if wait_outcome.was_cancelled:
        await finalize_noncritical(
            task_registry,
            task.task_id,
            TaskStatus.CANCELLED,
            error_message="Tool approval cancelled.",
            status_message="Cancelled",
            logger=logger,
            operation="agent.tool_approval_tasks.cancelled.finalize",
            log_message="Failed to finalize tool approval task after cancellation (non-critical).",
            details={"conv_id": conv_id, "task_id": task.task_id, "user_id": int(user_id)},
        )
        await delete_tool_approval_notification_noncritical(
            logger=logger,
            database_notifications=database_notifications,
            user_id=user_id,
            metadata=task.metadata,
            conv_id=conv_id,
            task_id=task.task_id,
            notification_id=notification_id,
        )
        return ToolApprovalTaskOutcome(approved=None, remember=False)
    completed = wait_outcome.task
    if completed is None:
        await delete_tool_approval_notification_noncritical(
            logger=logger,
            database_notifications=database_notifications,
            user_id=user_id,
            metadata=task.metadata,
            conv_id=conv_id,
            task_id=task.task_id,
            notification_id=notification_id,
        )
        return ToolApprovalTaskOutcome(approved=False, remember=False)
    outcome = _decode_approval_task_result(
        logger,
        task=completed,
        details={**details, "task_id": task.task_id},
    )
    await delete_tool_approval_notification_noncritical(
        logger=logger,
        database_notifications=database_notifications,
        user_id=user_id,
        metadata=task.metadata,
        conv_id=conv_id,
        task_id=task.task_id,
        notification_id=notification_id,
    )
    return outcome
