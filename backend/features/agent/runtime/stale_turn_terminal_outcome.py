"""SoAI - Stale running turn terminal outcome resolution [backend/features/agent/runtime/stale_turn_terminal_outcome.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_ABANDONED,
    AGENT_TURN_STATUS_ERROR,
)
from core.agent.turn_record_fields import (
    read_turn_optional_content_text,
    read_turn_optional_text,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_ERROR,
    is_active_tool_call_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "StaleTurnTerminalOutcome",
    "resolve_stale_turn_terminal_outcome",
)

_STALE_TOOL_FAILURE_ERROR_MESSAGE = (
    "Tool execution ended unexpectedly before the agent turn could be finalized."
)
_STALE_TOOL_FAILURE_ERROR_TYPE = "tool_call_error"


@dataclass(frozen=True, slots=True)
class StaleTurnTerminalOutcome:
    status: str
    error_message: str | None
    error_type: str | None


def _read_tool_call_error_message(tool_call: JSONDict) -> str | None:
    error_value = tool_call.get("error")
    if isinstance(error_value, str) and error_value.strip():
        return error_value.strip()
    result_value = tool_call.get("result")
    if not isinstance(result_value, dict):
        return None
    nested_error_value = result_value.get("error")
    if isinstance(nested_error_value, str) and nested_error_value.strip():
        return nested_error_value.strip()
    if isinstance(nested_error_value, dict):
        nested_message_value = nested_error_value.get("message")
        if isinstance(nested_message_value, str) and nested_message_value.strip():
            return nested_message_value.strip()
    return None


def _read_tool_call_error_type(tool_call: JSONDict) -> str | None:
    result_value = tool_call.get("result")
    if not isinstance(result_value, dict):
        return _STALE_TOOL_FAILURE_ERROR_TYPE
    code_value = result_value.get("code")
    if isinstance(code_value, str) and code_value.strip():
        return code_value.strip()
    nested_error_value = result_value.get("error")
    if isinstance(nested_error_value, dict):
        nested_code_value = nested_error_value.get("code")
        if isinstance(nested_code_value, str) and nested_code_value.strip():
            return nested_code_value.strip()
        nested_type_value = nested_error_value.get("type")
        if isinstance(nested_type_value, str) and nested_type_value.strip():
            return nested_type_value.strip()
    return _STALE_TOOL_FAILURE_ERROR_TYPE


def resolve_stale_turn_terminal_outcome(
    *,
    record: JSONDict,
    tool_calls: list[JSONDict],
) -> StaleTurnTerminalOutcome:
    turn_error_message = read_turn_optional_content_text(record, "error_message")
    turn_error_type = read_turn_optional_text(record, "error_type")
    if turn_error_message is not None or turn_error_type is not None:
        return StaleTurnTerminalOutcome(
            status=AGENT_TURN_STATUS_ERROR,
            error_message=turn_error_message,
            error_type=turn_error_type,
        )
    for tool_call in tool_calls:
        status_value = tool_call.get("status")
        status = status_value.strip().lower() if isinstance(status_value, str) else ""
        if status != TOOL_CALL_STATUS_ERROR:
            continue
        error_message = _read_tool_call_error_message(tool_call)
        return StaleTurnTerminalOutcome(
            status=AGENT_TURN_STATUS_ERROR,
            error_message=error_message or _STALE_TOOL_FAILURE_ERROR_MESSAGE,
            error_type=_read_tool_call_error_type(tool_call),
        )
    if any(
        is_active_tool_call_status(str(tool_call.get("status") or "")) for tool_call in tool_calls
    ):
        return StaleTurnTerminalOutcome(
            status=AGENT_TURN_STATUS_ERROR,
            error_message=_STALE_TOOL_FAILURE_ERROR_MESSAGE,
            error_type=_STALE_TOOL_FAILURE_ERROR_TYPE,
        )
    return StaleTurnTerminalOutcome(
        status=AGENT_TURN_STATUS_ABANDONED,
        error_message=None,
        error_type=None,
    )
