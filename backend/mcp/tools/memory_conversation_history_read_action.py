"""SoAI - MCP memory conversation history read action [backend/mcp/tools/memory_conversation_history_read_action.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError
from mcp.tools.memory_conversation_history_contracts import (
    DEFAULT_ROLES,
    coerce_text,
    normalize_conversation_record,
    require_conversation_history_message_metadata,
    require_database_conversations,
    require_database_messages,
)

if TYPE_CHECKING:
    from core.conversations.conversation_message_window import ConversationMessageCursor
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("action_read",)


def _build_not_found_response() -> JSONDict:
    return {
        "action": "read",
        "found": False,
        "conversation": None,
        "messages": [],
        "count": 0,
        "has_more": False,
        "next_before_timestamp": None,
        "next_before_message_id": None,
    }


async def action_read(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    include_automation: bool,
    conv_id: str,
    limit_messages: int,
    before_cursor: ConversationMessageCursor | None,
    max_chars_per_message: int,
) -> JSONDict:
    database_conversations = require_database_conversations(utility_tools)
    database_messages = require_database_messages(utility_tools)
    conversation = await database_conversations.get_conversation(conv_id, user_id)
    if conversation is None:
        return _build_not_found_response()
    if not isinstance(conversation, dict):
        raise MCPToolError(-32603, "Conversation metadata is invalid.")
    normalized_conversation = normalize_conversation_record(conversation)
    if (not include_automation) and bool(normalized_conversation.get("is_automation")):
        return _build_not_found_response()
    requested_limit = int(limit_messages)
    raw = await database_messages.get_messages_tail(
        conv_id,
        user_id,
        before_cursor=before_cursor,
        limit=requested_limit + 1,
        roles=DEFAULT_ROLES,
    )
    if raw is None:
        return _build_not_found_response()

    validated_messages_desc_all: list[tuple[JSONDict, int, str, int]] = []
    for message in raw:
        if not isinstance(message, dict):
            raise MCPToolError(-32603, "Conversation message metadata is invalid.")
        message_id, role, timestamp = require_conversation_history_message_metadata(message)
        validated_messages_desc_all.append((message, message_id, role, timestamp))
    has_more = len(validated_messages_desc_all) > requested_limit
    messages_desc = validated_messages_desc_all[:requested_limit]
    messages_desc_trimmed: list[JSONDict] = []
    for message, message_id, role, timestamp in messages_desc:
        content_value = message.get("content")
        content_text = coerce_text(content_value)
        truncated_content = content_text[:max_chars_per_message]
        messages_desc_trimmed.append(
            {
                "message_id": message_id,
                "role": role,
                "timestamp": timestamp,
                "content": truncated_content,
            },
        )
    messages_asc = list(reversed(messages_desc_trimmed))
    boundary_message_id: int | None = None
    boundary_timestamp: int | None = None
    if has_more and messages_desc:
        _, boundary_message_id, _, boundary_timestamp = messages_desc[-1]
    return {
        "action": "read",
        "found": True,
        "conversation": normalized_conversation,
        "messages": messages_asc,
        "count": len(messages_asc),
        "has_more": has_more,
        "next_before_timestamp": boundary_timestamp if has_more else None,
        "next_before_message_id": boundary_message_id if has_more else None,
    }
