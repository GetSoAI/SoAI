"""SoAI - MCP memory conversation history tool contracts [backend/mcp/tools/memory_conversation_history_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.formatting import timestamp_ms_to_utc_iso
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import require_positive_int_strict
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversation_records import (
        DatabaseConversationsProtocol,
    )
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "DEFAULT_ROLES",
    "build_excerpt",
    "coerce_text",
    "normalize_action",
    "normalize_conversation_record",
    "require_conversation_history_epoch_ms",
    "require_conversation_history_message_metadata",
    "require_database_conversations",
    "require_database_messages",
)

DEFAULT_ROLES: tuple[str, ...] = ("user", "assistant")


def _title_matches_generated_conversation_id(title: str) -> bool:
    normalized = title.strip() if title else ""
    if not normalized:
        return False
    if not normalized.startswith("conv_"):
        return False
    return re.fullmatch(r"conv_[0-9a-f]{8,}", normalized) is not None


def require_database_conversations(
    utility_tools: MCPUtilityToolsProtocol,
) -> DatabaseConversationsProtocol:
    database_conversations = utility_tools.database_conversations
    if database_conversations is None:
        raise MCPToolError(-32603, "Conversation storage is not available.")
    return database_conversations


def require_database_messages(
    utility_tools: MCPUtilityToolsProtocol,
) -> DatabaseMessagesProtocol:
    database_messages = utility_tools.database_messages
    if database_messages is None:
        raise MCPToolError(-32603, "Conversation message storage is not available.")
    return database_messages


def normalize_action(action_raw: JSONValue) -> str:
    if not isinstance(action_raw, str):
        raise ValidationError("action must be a string.")
    normalized = action_raw.strip().lower()
    if normalized not in {"list", "search", "read"}:
        raise ValidationError("action must be one of: list, search, read.")
    return normalized


def coerce_text(value: JSONValue) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, int | float | bool):
        return str(value)
    dumped: str | None = None
    try:
        dumped = serialize_json_compact_stable_strict(value, ensure_ascii=False)
    except (TypeError, ValueError):
        dumped = None
    if dumped is not None:
        return dumped
    return str(value)


def build_excerpt(*, text: str, query: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    normalized_text = text or ""
    normalized_query = query or ""
    lower_text = normalized_text.lower()
    lower_query = normalized_query.lower()
    idx = lower_text.find(lower_query) if lower_query else -1
    if idx < 0:
        return normalized_text[:max_chars]
    left_budget = max_chars // 2
    start = max(0, idx - left_budget)
    end = min(len(normalized_text), start + max_chars)
    if end - start < max_chars and start > 0:
        start = max(0, end - max_chars)
    return normalized_text[start:end]


def require_conversation_history_epoch_ms(
    record: JSONDict,
    *,
    key: str,
) -> int:
    try:
        return require_unix_epoch_ms(
            record.get(key),
            error_message="Conversation timestamp is invalid.",
            enforce_maximum=False,
        )
    except ValidationError as exception:
        raise MCPToolError(-32603, "Conversation metadata is invalid.") from exception


def require_conversation_history_message_metadata(
    record: JSONDict,
) -> tuple[int, str, int]:
    role_value = record.get("role")
    if not isinstance(role_value, str) or not role_value.strip():
        raise MCPToolError(-32603, "Conversation message metadata is invalid.")
    try:
        message_id = require_positive_int_strict(
            record.get("id"),
            error_message="Conversation message id is invalid.",
        )
        timestamp = require_unix_epoch_ms(
            record.get("timestamp"),
            error_message="Conversation message timestamp is invalid.",
            enforce_maximum=False,
        )
    except ValidationError as exception:
        raise MCPToolError(-32603, "Conversation message metadata is invalid.") from exception
    return (message_id, role_value, timestamp)


def normalize_conversation_record(record: JSONDict) -> JSONDict:
    conv_id_value = record.get("id")
    title_value = record.get("title")
    created_at_value = require_conversation_history_epoch_ms(record, key="created_at_ms")
    last_modified_value = require_conversation_history_epoch_ms(
        record,
        key="last_modified_at_ms",
    )
    if not isinstance(conv_id_value, str) or not conv_id_value.strip():
        raise MCPToolError(-32603, "Conversation metadata is invalid.")
    if not isinstance(title_value, str):
        raise MCPToolError(-32603, "Conversation metadata is invalid.")
    title = title_value.strip()
    if not title:
        raise MCPToolError(-32603, "Conversation metadata is invalid.")
    conv_id = conv_id_value.strip()
    title_is_generated = title == conv_id or _title_matches_generated_conversation_id(title)
    display_title = (
        f"Conversation {timestamp_ms_to_utc_iso(int(created_at_value))}"
        if title_is_generated
        else title
    )
    is_automation_value = record.get("is_automation")
    is_automation = bool(is_automation_value == 1 or is_automation_value is True)
    return {
        "conv_id": conv_id,
        "title": title,
        "display_title": display_title,
        "title_is_generated": title_is_generated,
        "created_at": int(created_at_value),
        "last_modified_at": int(last_modified_value),
        "is_automation": is_automation,
    }
