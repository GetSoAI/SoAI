"""SoAI - MCP utility tool: memory_conversation_history [backend/mcp/tools/memory_conversation_history_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_message_window import ConversationMessageCursor
from core.errors.exceptions import ValidationError
from core.validation.booleans import parse_bool_flag_with_default
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import require_positive_int_strict
from mcp.tools.argument_fields import require_non_empty_string
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.memory_conversation_history_contracts import normalize_action
from mcp.tools.memory_conversation_history_list_action import action_list
from mcp.tools.memory_conversation_history_read_action import action_read
from mcp.tools.memory_conversation_history_search_action import action_search
from mcp.tools.openai_owner_context import require_openai_conversation_owner

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_memory_conversation_history",)


def _parse_list_cursor(arguments: JSONDict) -> tuple[int | None, str | None]:
    timestamp_raw = arguments.get("last_modified_before")
    conv_id_raw = arguments.get("last_modified_before_conv_id")
    if timestamp_raw is None and conv_id_raw is None:
        return (None, None)
    if timestamp_raw is None or conv_id_raw is None:
        raise MCPToolError(
            -32602,
            "last_modified_before and last_modified_before_conv_id must be provided together.",
        )
    try:
        timestamp = require_unix_epoch_ms(
            timestamp_raw,
            error_message="last_modified_before must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    conv_id = require_non_empty_string(
        conv_id_raw,
        key="last_modified_before_conv_id",
    )
    return (timestamp, conv_id)


def _parse_message_cursor(arguments: JSONDict) -> ConversationMessageCursor | None:
    timestamp_raw = arguments.get("before_timestamp")
    message_id_raw = arguments.get("before_message_id")
    if timestamp_raw is None and message_id_raw is None:
        return None
    if timestamp_raw is None or message_id_raw is None:
        raise MCPToolError(
            -32602,
            "before_timestamp and before_message_id must be provided together.",
        )
    try:
        timestamp = require_unix_epoch_ms(
            timestamp_raw,
            error_message="before_timestamp must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
        message_id = require_positive_int_strict(
            message_id_raw,
            error_message="before_message_id must be a positive integer.",
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    return ConversationMessageCursor(created_at_ms=timestamp, id=message_id)


async def _resolve_default_include_automation(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    conv_id: str,
) -> bool:
    database_conversations = utility_tools.database_conversations
    if database_conversations is None:
        return False
    conversation = await database_conversations.get_conversation(conv_id, user_id)
    if not isinstance(conversation, dict):
        return False
    is_automation_value = conversation.get("is_automation")
    return bool(is_automation_value == 1 or is_automation_value is True)


async def tool_memory_conversation_history(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    user_id, current_conv_id = require_openai_conversation_owner(
        owner_key,
        tool_name="memory_conversation_history",
    )
    action = normalize_action(get_arg(arguments, "action"))
    include_automation_raw = arguments.get("include_automation")
    if include_automation_raw is None:
        include_automation = await _resolve_default_include_automation(
            utility_tools,
            user_id=user_id,
            conv_id=current_conv_id,
        )
    else:
        include_automation = parse_bool_flag_with_default(
            include_automation_raw,
            default=False,
        )
    if action == "list":
        limit = parse_int(arguments.get("limit"), default=25, min_value=1, max_value=100)
        last_modified_before, last_modified_before_conv_id = _parse_list_cursor(arguments)
        return await action_list(
            utility_tools,
            user_id=user_id,
            include_automation=include_automation,
            limit=limit,
            last_modified_before=last_modified_before,
            last_modified_before_conv_id=last_modified_before_conv_id,
        )
    if action == "search":
        query = str(get_arg(arguments, "query") or "").strip()
        if not query:
            raise MCPToolError(-32602, "query must be a non-empty string.")
        limit_matches = parse_int(
            arguments.get("limit_matches"),
            default=20,
            min_value=1,
            max_value=100,
        )
        limit_conversations = parse_int(
            arguments.get("limit_conversations"),
            default=5,
            min_value=1,
            max_value=25,
        )
        matches_per_conversation = parse_int(
            arguments.get("matches_per_conversation"),
            default=5,
            min_value=1,
            max_value=20,
        )
        max_chars_per_match = parse_int(
            arguments.get("max_chars_per_match"),
            default=500,
            min_value=50,
            max_value=4000,
        )
        return await action_search(
            utility_tools,
            user_id=user_id,
            include_automation=include_automation,
            query=query,
            limit_matches=limit_matches,
            limit_conversations=limit_conversations,
            matches_per_conversation=matches_per_conversation,
            max_chars_per_match=max_chars_per_match,
        )
    conv_id_raw = get_arg(arguments, "conv_id")
    conv_id = conv_id_raw.strip() if isinstance(conv_id_raw, str) else ""
    if not conv_id:
        raise MCPToolError(-32602, "conv_id must be a non-empty string.")
    limit_messages = parse_int(
        arguments.get("limit_messages"),
        default=50,
        min_value=1,
        max_value=200,
    )
    before_cursor = _parse_message_cursor(arguments)
    max_chars_per_message = parse_int(
        arguments.get("max_chars_per_message"),
        default=4000,
        min_value=1,
        max_value=20000,
    )
    return await action_read(
        utility_tools,
        user_id=user_id,
        include_automation=include_automation,
        conv_id=conv_id,
        limit_messages=limit_messages,
        before_cursor=before_cursor,
        max_chars_per_message=max_chars_per_message,
    )
