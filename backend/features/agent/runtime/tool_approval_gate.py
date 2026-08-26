"""SoAI - Agent tool approval gate helpers [backend/features/agent/runtime/tool_approval_gate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.tool_approval.permission_key import resolve_tool_approval_permission_key
from features.agent.runtime.tool_approval_tasks import await_tool_approval_outcome

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import CancellationHistoryProtocol
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.types.json import JSONValue

__all__ = ("resolve_tool_approval_decision",)

OPERATION_DESTRUCTIVE_HINT = "agent.tool_approval_gate.destructive_hint"


def _resolve_requires_tool_approval(
    *,
    tool_context: MCPToolContext,
    tool_name: str,
    logger: LoggerProtocol,
    details: Mapping[str, JSONValue],
) -> bool:
    tool_entry = tool_context.tool_map.get(tool_name)
    if not isinstance(tool_entry, Mapping):
        _log_destructive_hint_warning(
            logger,
            message="Tool metadata is missing for tool approval; requiring approval.",
            details={**details, "tool_name": tool_name},
        )
        return True
    raw_value = tool_entry.get("raw")
    raw = raw_value if isinstance(raw_value, Mapping) else None
    annotations_value = raw.get("annotations") if raw is not None else None
    annotations = annotations_value if isinstance(annotations_value, Mapping) else None
    destructive_hint = annotations.get("destructiveHint") if annotations is not None else None
    if destructive_hint is True:
        return True
    requires_approval_hint = (
        annotations.get("requiresApprovalHint") if annotations is not None else None
    )
    if requires_approval_hint is True:
        return True
    if destructive_hint is False:
        return False
    _log_destructive_hint_warning(
        logger,
        message="Tool metadata destructiveHint is missing or invalid; requiring approval.",
        details={**details, "tool_name": tool_name, "destructiveHint": destructive_hint},
    )
    return True


def _log_destructive_hint_warning(
    logger: LoggerProtocol,
    *,
    message: str,
    details: Mapping[str, JSONValue],
) -> None:
    exception = ValidationError(message, operation=OPERATION_DESTRUCTIVE_HINT)
    log_exception(
        logger,
        exception,
        message=message,
        operation=OPERATION_DESTRUCTIVE_HINT,
        level="warning",
        details=dict(details),
    )


async def resolve_tool_approval_decision(
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    task_registry: TaskRegistryProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    conversation_attention: ConversationAttentionCoordinatorProtocol,
    cancellation_history: CancellationHistoryProtocol | None,
    cancellation_id: str,
    logger: LoggerProtocol,
    turn_id: str,
    iteration_index: int,
    tool_call_id: str,
    tool_name: str,
    tool_arguments: str | None,
    approved_tool_permissions: set[str] | None = None,
) -> bool | None:
    normalized_tool_name = tool_name.strip()
    if not normalized_tool_name:
        return True
    if not tool_context.tool_approval_required:
        return True
    if not request_context.interactive_tool_approval:
        return True
    if tool_context.user_id <= 0:
        return True
    conv_id = str(tool_context.conv_id or "").strip()
    if not conv_id:
        return True
    details: dict[str, JSONValue] = {
        "conv_id": conv_id,
        "user_id": int(tool_context.user_id),
        "turn_id": turn_id,
        "iteration_index": int(iteration_index),
        "tool_call_id": tool_call_id,
    }
    requires_approval = _resolve_requires_tool_approval(
        tool_context=tool_context,
        tool_name=normalized_tool_name,
        logger=logger,
        details=details,
    )
    if not requires_approval:
        return True
    permission_key = resolve_tool_approval_permission_key(
        tool_name=normalized_tool_name,
        tool_arguments=tool_arguments,
    )
    if approved_tool_permissions is not None and permission_key in approved_tool_permissions:
        return True
    outcome = await await_tool_approval_outcome(
        task_registry=task_registry,
        database_notifications=database_notifications,
        conversation_attention=conversation_attention,
        cancellation_history=cancellation_history,
        cancellation_id=cancellation_id,
        logger=logger,
        request_context=request_context,
        user_id=int(tool_context.user_id),
        conv_id=conv_id,
        turn_id=turn_id,
        iteration_index=iteration_index,
        tool_call_id=tool_call_id,
        tool_name=normalized_tool_name,
        tool_key=permission_key,
        tool_arguments=tool_arguments,
        user_interaction_timeout_ms=tool_context.user_interaction_timeout_ms,
    )
    if approved_tool_permissions is not None and outcome.approved is True and outcome.remember:
        approved_tool_permissions.add(permission_key)
    return outcome.approved
