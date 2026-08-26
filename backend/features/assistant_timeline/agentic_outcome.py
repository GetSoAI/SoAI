"""SoAI - Shared assistant timeline agentic terminal outcome helpers [backend/features/assistant_timeline/agentic_outcome.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_defaults import resolve_agent_turn_terminal_defaults
from core.agent.status_values import (
    AGENT_TURN_STATUS_ABANDONED,
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_ERROR,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
)
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resolve_agentic_terminal_outcome",)


def _completed_turn_has_visible_output(turn_state: JSONDict) -> bool:
    if coerce_optional_trimmed_str(turn_state.get("assistant_text")) is not None:
        return True
    tool_calls = turn_state.get("tool_calls")
    return isinstance(tool_calls, list) and bool(tool_calls)


def resolve_agentic_terminal_outcome(
    turn_state: JSONDict | None,
) -> tuple[str, str | None, str | None]:
    if turn_state is None:
        return (
            AGENT_TURN_STATUS_ERROR,
            "Agent turn state is unavailable after stream completion.",
            "server_error",
        )
    status_value = turn_state.get("status")
    status = status_value.strip().lower() if isinstance(status_value, str) else ""
    error_message = coerce_optional_trimmed_str(turn_state.get("error_message"))
    error_type = coerce_optional_trimmed_str(turn_state.get("error_type"))
    if status == AGENT_TURN_STATUS_COMPLETED:
        if not _completed_turn_has_visible_output(turn_state):
            return (
                TOOL_CALL_STATUS_ERROR,
                "Agent turn completed without producing assistant output.",
                "empty_response",
            )
        return (TOOL_CALL_STATUS_COMPLETED, None, None)
    if status == AGENT_TURN_STATUS_CANCELLED:
        _, default_error_message, default_error_type = resolve_agent_turn_terminal_defaults(
            AGENT_TURN_STATUS_CANCELLED,
        )
        return (
            TOOL_CALL_STATUS_CANCELLED,
            error_message or default_error_message or "Agent turn cancelled.",
            error_type or default_error_type or TOOL_CALL_STATUS_CANCELLED,
        )
    if status == AGENT_TURN_STATUS_ERROR:
        _, default_error_message, default_error_type = resolve_agent_turn_terminal_defaults(
            AGENT_TURN_STATUS_ERROR,
        )
        return (
            TOOL_CALL_STATUS_ERROR,
            error_message or default_error_message or "Agent turn failed.",
            error_type or default_error_type or "server_error",
        )
    if status == AGENT_TURN_STATUS_MAX_ITERATIONS:
        return (TOOL_CALL_STATUS_COMPLETED, None, None)
    if status == AGENT_TURN_STATUS_ABANDONED:
        _, default_error_message, default_error_type = resolve_agent_turn_terminal_defaults(
            AGENT_TURN_STATUS_ABANDONED,
        )
        return (
            TOOL_CALL_STATUS_ERROR,
            error_message or default_error_message or "Agent turn was abandoned before completion.",
            error_type or default_error_type or AGENT_TURN_STATUS_ABANDONED,
        )
    return (
        TOOL_CALL_STATUS_ERROR,
        "Agent turn terminal status is unavailable after stream completion.",
        "server_error",
    )
