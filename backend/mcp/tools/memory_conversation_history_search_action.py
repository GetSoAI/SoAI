"""SoAI - MCP memory conversation history search action [backend/mcp/tools/memory_conversation_history_search_action.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError
from mcp.tools.memory_conversation_history_contracts import (
    DEFAULT_ROLES,
    build_excerpt,
    coerce_text,
    require_conversation_history_epoch_ms,
    require_conversation_history_message_metadata,
    require_database_messages,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("action_search",)


async def action_search(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    include_automation: bool,
    query: str,
    limit_matches: int,
    limit_conversations: int,
    matches_per_conversation: int,
    max_chars_per_match: int,
) -> JSONDict:
    database_messages = require_database_messages(utility_tools)
    matches = await database_messages.search_messages_by_content(
        user_id,
        query=query,
        limit=limit_matches,
        include_automation=include_automation,
        roles=DEFAULT_ROLES,
    )
    grouped: dict[str, JSONDict] = {}
    total_matches = 0
    for item in matches:
        if not isinstance(item, dict):
            raise MCPToolError(-32603, "Conversation metadata is invalid.")
        conv_id_value = item.get("conv_id")
        title_value = item.get("title")
        last_modified_value = require_conversation_history_epoch_ms(
            item,
            key="last_modified_at_ms",
        )
        message_value = item.get("message")
        if not isinstance(conv_id_value, str) or not conv_id_value.strip():
            raise MCPToolError(-32603, "Conversation metadata is invalid.")
        if not isinstance(title_value, str):
            raise MCPToolError(-32603, "Conversation metadata is invalid.")
        if not isinstance(message_value, dict):
            raise MCPToolError(-32603, "Conversation message metadata is invalid.")
        if conv_id_value not in grouped:
            if len(grouped) >= limit_conversations:
                continue
            grouped[conv_id_value] = {
                "conv_id": conv_id_value,
                "title": title_value,
                "last_modified_at": int(last_modified_value),
                "matches": [],
            }
        group_matches = grouped[conv_id_value].get("matches")
        if not isinstance(group_matches, list):
            raise MCPToolError(-32603, "Conversation search projection is invalid.")
        if len(group_matches) >= matches_per_conversation:
            continue
        message_id_value, role_value, timestamp_value = (
            require_conversation_history_message_metadata(message_value)
        )
        content_value = message_value.get("content")
        excerpt = build_excerpt(
            text=coerce_text(content_value),
            query=query,
            max_chars=max_chars_per_match,
        )
        group_matches.append(
            {
                "message_id": message_id_value,
                "role": role_value,
                "timestamp": int(timestamp_value),
                "excerpt": excerpt,
            },
        )
        total_matches += 1
    return {
        "action": "search",
        "query": query,
        "results": list(grouped.values()),
        "count_conversations": len(grouped),
        "count_matches_total": total_matches,
        "count": len(grouped),
    }
