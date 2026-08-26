"""SoAI - Subagent parent tool call status/result mapping [backend/features/agent/subagents/parent_tool_call_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_ABANDONED,
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_terminal_tool_result",
    "resolve_parent_tool_call_error_message",
    "resolve_parent_tool_call_status",
)


def resolve_parent_tool_call_status(subagent_status: str) -> str:
    normalized = str(subagent_status or "").strip()
    if normalized in (AGENT_TURN_STATUS_COMPLETED, AGENT_TURN_STATUS_MAX_ITERATIONS):
        return TOOL_CALL_STATUS_COMPLETED
    if normalized == AGENT_TURN_STATUS_CANCELLED:
        return TOOL_CALL_STATUS_CANCELLED
    if normalized == AGENT_TURN_STATUS_ABANDONED:
        return TOOL_CALL_STATUS_ERROR
    return TOOL_CALL_STATUS_ERROR


def resolve_parent_tool_call_error_message(
    *,
    parent_status: str,
    subagent_status: str,
    error_message: str | None,
) -> str | None:
    if parent_status == TOOL_CALL_STATUS_COMPLETED:
        return None
    normalized_message = str(error_message or "").strip()
    if normalized_message:
        return normalized_message
    normalized_subagent_status = str(subagent_status or "").strip()
    if parent_status == TOOL_CALL_STATUS_CANCELLED:
        return "Subagent cancelled."
    if normalized_subagent_status:
        return f"Subagent finished with status '{normalized_subagent_status}'."
    return "Subagent failed."


def build_terminal_tool_result(
    *,
    result_payload: JSONDict | None,
    token_usage: JSONDict | None,
) -> JSONValue | None:
    if result_payload is not None:
        return result_payload
    if token_usage is not None:
        return {"token_usage": token_usage}
    return None
