"""SoAI - MCP utility tool definition: stop_conversation [backend/mcp/tools/utility_tool_definitions/stop_conversation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from core.tool_calls.conversation_stop_signal import (
    STOP_CONVERSATION_REASON_MODEL_REQUESTED,
    STOP_CONVERSATION_SCOPE_CURRENT_TURN,
    STOP_CONVERSATION_STATUS_STOPPED,
    STOP_CONVERSATION_TOOL_NAME,
)
from mcp.tools.icons import ICON_STOP

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_stop_conversation_tool_definitions",)


def build_stop_conversation_tool_definitions() -> dict[str, JSONDict]:
    return {
        STOP_CONVERSATION_TOOL_NAME: {
            "title": "Stop Conversation",
            "description": (
                "Stop the current model turn cleanly without closing the conversation."
            ),
            "icons": [build_tool_icon_entry(ICON_STOP)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
                "required": [],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    STOP_CONVERSATION_TOOL_NAME: {"type": "boolean", "enum": [True]},
                    "scope": {"type": "string", "enum": [STOP_CONVERSATION_SCOPE_CURRENT_TURN]},
                    "status": {"type": "string", "enum": [STOP_CONVERSATION_STATUS_STOPPED]},
                    "reason": {
                        "type": "string",
                        "enum": [STOP_CONVERSATION_REASON_MODEL_REQUESTED],
                    },
                    "conv_id": {"type": "string"},
                    "turn_id": {"type": "string"},
                    "iteration_index": {"type": ["integer", "null"]},
                },
                "required": [
                    STOP_CONVERSATION_TOOL_NAME,
                    "scope",
                    "status",
                    "reason",
                    "conv_id",
                    "turn_id",
                    "iteration_index",
                ],
            },
            "annotations": build_tool_annotation_flags(),
        },
    }
