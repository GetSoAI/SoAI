"""SoAI - MCP utility tool definitions: memory_conversation_history [backend/mcp/tools/utility_tool_definitions/memory_conversation_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_MEMORY

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_memory_conversation_history_tool_definitions",)


def build_memory_conversation_history_tool_definitions() -> dict[str, JSONDict]:
    return {
        "memory_conversation_history": {
            "title": "Conversation History",
            "description": (
                "List, search, and read the user's past chat conversations. "
                "Defaults to user+assistant messages only. When called from an automation "
                "conversation, automation conversations are included by default; otherwise "
                "they are excluded unless include_automation is set."
            ),
            "icons": [build_tool_icon_entry(ICON_MEMORY)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "search", "read"],
                        "description": "Action to perform: list, search, or read.",
                    },
                    "include_automation": {
                        "type": "boolean",
                        "description": "When true, include automation conversations (is_automation=1). When omitted, defaults to true inside an automation conversation and false otherwise.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "For action=list: max conversations to return (default 25, max 100).",
                    },
                    "last_modified_before": {
                        "type": "integer",
                        "description": "For action=list: epoch-millisecond pagination cursor. Must be paired with last_modified_before_conv_id.",
                    },
                    "last_modified_before_conv_id": {
                        "type": "string",
                        "description": "For action=list: conversation-id tie-breaker paired with last_modified_before.",
                    },
                    "query": {
                        "type": "string",
                        "description": "For action=search: case-insensitive substring to search in message content.",
                    },
                    "limit_matches": {
                        "type": "integer",
                        "description": "For action=search: max matching messages to scan/return (default 20, max 100).",
                    },
                    "limit_conversations": {
                        "type": "integer",
                        "description": "For action=search: max conversations to include in results (default 5, max 25).",
                    },
                    "matches_per_conversation": {
                        "type": "integer",
                        "description": "For action=search: max matches per conversation (default 5, max 20).",
                    },
                    "max_chars_per_match": {
                        "type": "integer",
                        "description": "For action=search: excerpt length per match (default 500, max 4000).",
                    },
                    "conv_id": {
                        "type": "string",
                        "description": "For action=read: conversation id to read.",
                    },
                    "limit_messages": {
                        "type": "integer",
                        "description": "For action=read: max messages to return (default 50, max 200).",
                    },
                    "before_timestamp": {
                        "type": "integer",
                        "description": "For action=read: epoch-millisecond cursor paired with before_message_id.",
                    },
                    "before_message_id": {
                        "type": "integer",
                        "description": "For action=read: message-id tie-breaker paired with before_timestamp.",
                    },
                    "max_chars_per_message": {
                        "type": "integer",
                        "description": "For action=read: max chars per message content (default 4000, max 20000).",
                    },
                },
                "required": ["action"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {"type": "string"},
                    "count": {"type": "integer"},
                    "conversations": {"type": "array", "items": {"type": "object"}},
                    "next_last_modified_before": {"type": ["integer", "null"]},
                    "next_last_modified_before_conv_id": {"type": ["string", "null"]},
                    "query": {"type": ["string", "null"]},
                    "results": {"type": "array", "items": {"type": "object"}},
                    "count_conversations": {"type": "integer"},
                    "count_matches_total": {"type": "integer"},
                    "found": {"type": "boolean"},
                    "conversation": {"type": ["object", "null"]},
                    "messages": {"type": "array", "items": {"type": "object"}},
                    "has_more": {"type": "boolean"},
                    "next_before_timestamp": {"type": ["integer", "null"]},
                    "next_before_message_id": {"type": ["integer", "null"]},
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
    }
