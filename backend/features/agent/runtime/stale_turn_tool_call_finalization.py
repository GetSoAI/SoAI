"""SoAI - Stale turn root tool-call terminal finalization [backend/features/agent/runtime/stale_turn_tool_call_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_ABANDONED
from core.errors.exception_logging import log_handled_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tool_calls.owner_task_reconciliation import (
    reconcile_tool_call_owner_task_terminal_state,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_ERROR,
    is_active_tool_call_status,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict

__all__ = ("finalize_stale_turn_active_tool_calls_noncritical",)

_OPERATION = "features.agent.runtime.finalize_stale_turn_active_tool_calls"


def _resolve_tool_call_terminal_error_message(turn_status: str, error_message: str | None) -> str:
    normalized_error_message = str(error_message or "").strip()
    if turn_status == AGENT_TURN_STATUS_ABANDONED:
        return (
            normalized_error_message or "Tool call cancelled because the agent turn was abandoned."
        )
    return (
        normalized_error_message or "Tool call failed because the agent turn ended with an error."
    )


def _resolve_tool_call_terminal_status(turn_status: str) -> str:
    if turn_status == AGENT_TURN_STATUS_ABANDONED:
        return TOOL_CALL_STATUS_CANCELLED
    return TOOL_CALL_STATUS_ERROR


async def finalize_stale_turn_active_tool_calls_noncritical(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry: TaskRegistryLifecycleView | None,
    tool_calls: list[JSONDict],
    turn_status: str,
    turn_error_message: str | None,
    completed_at_ms: int,
    logger: LoggerProtocol,
) -> None:
    tool_status = _resolve_tool_call_terminal_status(turn_status)
    error_message = _resolve_tool_call_terminal_error_message(turn_status, turn_error_message)
    for tool_call in tool_calls:
        storage_call_id = str(tool_call.get("id") or "").strip()
        if not storage_call_id:
            continue
        if not is_active_tool_call_status(str(tool_call.get("status") or "")):
            continue
        try:
            persisted = await database_tool_calls.finalize_tool_call_if_unfinished(
                storage_call_id,
                status=tool_status,
                error_message=error_message,
                completed_at_ms=completed_at_ms,
            )
            if task_registry is not None and isinstance(persisted, dict):
                await reconcile_tool_call_owner_task_terminal_state(
                    task_registry=task_registry,
                    tool_call=persisted,
                    terminal_status=tool_status,
                    terminal_message=error_message,
                )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to finalize stale active tool call after turn reconciliation.",
                operation=_OPERATION,
                details={"storage_call_id": storage_call_id, "turn_status": turn_status},
                level="warning",
            )
