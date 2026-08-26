"""SoAI - MCP memory conversation history list action [backend/mcp/tools/memory_conversation_history_list_action.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from mcp.tools.error import MCPToolError
from mcp.tools.memory_conversation_history_contracts import (
    normalize_conversation_record,
    require_database_conversations,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("action_list",)


async def action_list(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    include_automation: bool,
    limit: int,
    last_modified_before: int | None,
    last_modified_before_conv_id: str | None,
) -> JSONDict:
    database_conversations = require_database_conversations(utility_tools)
    conversations = await database_conversations.list_conversations(user_id)
    filtered: list[tuple[int, str, JSONDict]] = []
    for record in conversations:
        if not isinstance(record, dict):
            raise MCPToolError(-32603, "Conversation metadata is invalid.")
        normalized = normalize_conversation_record(record)
        conv_id_value = normalized.get("conv_id")
        title_value = normalized.get("title")
        created_at_value = normalized.get("created_at")
        last_modified_value = normalized.get("last_modified_at")
        is_automation_value = normalized.get("is_automation")
        if not isinstance(conv_id_value, str) or not conv_id_value.strip():
            raise MCPToolError(-32603, "Conversation metadata is invalid.")
        if not isinstance(title_value, str) or not title_value.strip():
            raise MCPToolError(-32603, "Conversation metadata is invalid.")
        if not is_strict_int(created_at_value):
            raise MCPToolError(-32603, "Conversation metadata is invalid.")
        if not is_strict_int(last_modified_value):
            raise MCPToolError(-32603, "Conversation metadata is invalid.")
        if not isinstance(is_automation_value, bool):
            raise MCPToolError(-32603, "Conversation metadata is invalid.")
        if (not include_automation) and is_automation_value:
            continue
        if last_modified_before is not None and last_modified_before_conv_id is not None:
            if last_modified_value > last_modified_before:
                continue
            if (
                last_modified_value == last_modified_before
                and conv_id_value <= last_modified_before_conv_id
            ):
                continue
        filtered.append(
            (
                last_modified_value,
                conv_id_value,
                {
                    "conv_id": conv_id_value,
                    "title": title_value,
                    "created_at": created_at_value,
                    "last_modified_at": last_modified_value,
                    "is_automation": is_automation_value,
                },
            ),
        )

    filtered.sort(key=lambda item: (-item[0], item[1]))
    limited_entries = filtered[:limit]
    limited = [entry for _, _, entry in limited_entries]
    has_more = len(filtered) > len(limited_entries)
    next_cursor = limited_entries[-1][0] if has_more and limited_entries else None
    next_cursor_conv_id = limited_entries[-1][1] if has_more and limited_entries else None
    return {
        "action": "list",
        "conversations": limited,
        "count": len(limited),
        "next_last_modified_before": next_cursor,
        "next_last_modified_before_conv_id": next_cursor_conv_id,
    }
