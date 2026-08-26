"""SoAI - Conversation stop tool signal contract [backend/core/tool_calls/conversation_stop_signal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.record_fields import require_non_empty_str, require_optional_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "STOP_CONVERSATION_REASON_MODEL_REQUESTED",
    "STOP_CONVERSATION_SCOPE_CURRENT_TURN",
    "STOP_CONVERSATION_STATUS_STOPPED",
    "STOP_CONVERSATION_TOOL_NAME",
    "build_stop_conversation_signal",
    "is_stop_conversation_signal",
)

STOP_CONVERSATION_REASON_MODEL_REQUESTED = "model_requested_stop"
STOP_CONVERSATION_SCOPE_CURRENT_TURN = "current_turn"
STOP_CONVERSATION_STATUS_STOPPED = "stopped"
STOP_CONVERSATION_TOOL_NAME = "stop_conversation"


def build_stop_conversation_signal(
    *,
    conv_id: str,
    turn_id: str,
    iteration_index: int | None,
) -> JSONDict:
    normalized_conv_id = require_non_empty_str(
        conv_id,
        label="stop_conversation.conv_id",
        build_error=ValidationError,
    )
    normalized_turn_id = require_non_empty_str(
        turn_id,
        label="stop_conversation.turn_id",
        build_error=ValidationError,
    )
    normalized_iteration_index = require_optional_int(
        iteration_index,
        label="stop_conversation.iteration_index",
        build_error=ValidationError,
        minimum=0,
    )
    return {
        "stop_conversation": True,
        "scope": STOP_CONVERSATION_SCOPE_CURRENT_TURN,
        "status": STOP_CONVERSATION_STATUS_STOPPED,
        "reason": STOP_CONVERSATION_REASON_MODEL_REQUESTED,
        "conv_id": normalized_conv_id,
        "turn_id": normalized_turn_id,
        "iteration_index": normalized_iteration_index,
    }


def is_stop_conversation_signal(value: JSONValue) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        value.get("stop_conversation") is True
        and value.get("scope") == STOP_CONVERSATION_SCOPE_CURRENT_TURN
        and value.get("status") == STOP_CONVERSATION_STATUS_STOPPED
        and value.get("reason") == STOP_CONVERSATION_REASON_MODEL_REQUESTED
    )
