"""SoAI - Stale running turn terminal outcome resolution [backend/features/agent/runtime/stale_turn_terminal_outcome.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_ABANDONED,
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_ERROR,
)
from core.agent.turn_record_fields import (
    read_turn_optional_content_text,
    read_turn_optional_text,
)
from core.runtime.shutdown_errors import SERVER_SHUTDOWN_MESSAGE
from core.tool_calls.status_values import is_active_tool_call_status

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


def resolve_stale_turn_terminal_outcome(
    *,
    record: JSONDict,
    tool_calls: list[JSONDict],
    shutdown_requested: bool = False,
) -> StaleTurnTerminalOutcome:
    turn_error_message = read_turn_optional_content_text(record, "error_message")
    turn_error_type = read_turn_optional_text(record, "error_type")
    if turn_error_message is not None or turn_error_type is not None:
        return StaleTurnTerminalOutcome(
            status=AGENT_TURN_STATUS_ERROR,
            error_message=turn_error_message,
            error_type=turn_error_type,
        )
    if shutdown_requested:
        return StaleTurnTerminalOutcome(
            status=AGENT_TURN_STATUS_CANCELLED,
            error_message=SERVER_SHUTDOWN_MESSAGE,
            error_type=AGENT_TURN_STATUS_CANCELLED,
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
