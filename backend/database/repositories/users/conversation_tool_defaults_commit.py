"""SoAI - Narrow compare-and-set conversation tool-default repair [backend/database/repositories/users/conversation_tool_defaults_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.settings_commit import ConversationToolDefaultsCommitResult
from core.errors.exceptions import StateError
from core.openai.model_settings_validation import validate_model_settings
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue, is_str_list
from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.conversation_event_outbox import (
    sync_enqueue_conversation_updated_event,
)
from database.repositories.users.conversation_sync_operations import sync_get_conversation
from database.repositories.users.conversation_versioning import NEXT_LAST_MODIFIED_SQL
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.internal_protocols import DatabaseDomainEventOwnerProtocol

__all__ = (
    "reconcile_conversation_tool_defaults_method",
    "sync_reconcile_conversation_tool_defaults",
)

_TOOL_FIELDS = frozenset({"default_tools", "plan_tools", "execute_tools"})


def _read_tool_names(value: JSONValue | None) -> list[str] | None:
    if not is_str_list(value):
        return None
    return list(value)


def _require_last_modified(conversation: JSONDict) -> int:
    value = conversation.get("last_modified_at_ms")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise StateError("Repaired conversation has invalid last_modified_at_ms.")
    return value


def sync_reconcile_conversation_tool_defaults(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    tool_field: str,
    expected_tools_enabled: bool,
    expected_tools: list[str],
    tools_enabled: bool,
    updated_tools: list[str],
) -> ConversationToolDefaultsCommitResult:
    if tool_field not in _TOOL_FIELDS:
        raise StateError("Tool-default repair field is invalid.")
    existing = sync_get_conversation(conn, conv_id, user_id)
    if existing is None:
        return ConversationToolDefaultsCommitResult("not_found")
    settings = validate_model_settings(existing.get("model_settings"))
    mcp_value = settings.get("mcp")
    if not isinstance(mcp_value, dict):
        raise StateError("Conversation MCP settings are invalid.")
    current_enabled = mcp_value.get("tools_enabled")
    current_tools = _read_tool_names(mcp_value.get(tool_field))
    if current_enabled is not expected_tools_enabled or current_tools != expected_tools:
        return ConversationToolDefaultsCommitResult("superseded")
    if current_enabled is tools_enabled and current_tools == updated_tools:
        return ConversationToolDefaultsCommitResult("unchanged")
    next_mcp: JSONDict = dict(mcp_value)
    next_mcp["tools_enabled"] = tools_enabled
    next_mcp[tool_field] = list(updated_tools)
    next_settings: JSONDict = dict(settings)
    next_settings["mcp"] = next_mcp
    validated = validate_model_settings(next_settings)
    update_time = int(epoch_ms())
    updated = conn.execute(
        f"""UPDATE webui_conversations
            SET model_settings = ?, last_modified_at_ms = {NEXT_LAST_MODIFIED_SQL}
            WHERE id = ? AND user_id = ?""",
        (
            serialize_json_compact_stable_strict(validated),
            update_time,
            update_time,
            conv_id,
            user_id,
        ),
    ).rowcount
    if updated != 1:
        raise StateError("Conversation disappeared during tool-default repair.")
    authoritative = sync_get_conversation(conn, conv_id, user_id)
    if authoritative is None:
        raise StateError("Conversation disappeared after tool-default repair.")
    sync_enqueue_conversation_updated_event(
        conn,
        created_at_ms=update_time,
        user_id=user_id,
        conv_id=conv_id,
        last_modified_at_ms=_require_last_modified(authoritative),
        model_settings=validated,
    )
    return ConversationToolDefaultsCommitResult("updated")


async def reconcile_conversation_tool_defaults_method(
    self: DatabaseDomainEventOwnerProtocol,
    *,
    conv_id: str,
    user_id: int,
    tool_field: str,
    expected_tools_enabled: bool,
    expected_tools: list[str],
    tools_enabled: bool,
    updated_tools: list[str],
) -> ConversationToolDefaultsCommitResult:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
    result = await self.core.writer.queue_write_operation(
        sync_reconcile_conversation_tool_defaults,
        conv_id,
        user_id,
        tool_field,
        expected_tools_enabled,
        expected_tools,
        tools_enabled,
        updated_tools,
    )
    if result.status == "updated":
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
    return result
