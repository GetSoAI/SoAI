"""SoAI - Context compaction boundary removal transaction [backend/database/repositories/users/context_compaction_boundary_removal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.assistant_timeline.tool_event_payload_contract import (
    build_tool_event_payload_preview,
)
from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.errors.exceptions import ConflictError, ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.timing.epoch import epoch_ms
from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_TOOL_NAME,
    is_context_compaction_result_boundary_removed,
    mark_context_compaction_result_boundary_removed,
)
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
    sync_load_conversation_last_modified_at_ms,
    sync_require_expected_conversation_version,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("sync_remove_context_compaction_boundary",)

_BOUNDARY_REMOVED_REASON = "user_removed"


def _require_no_running_agent_turn(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT turn_id
            FROM webui_agent_turns
            WHERE conv_id = ?
              AND user_id = ?
              AND status = 'running'
            LIMIT 1
            """,
            (conv_id, int(user_id)),
        ),
    )
    if row is not None:
        raise ConflictError("Compaction unavailable while agent is running.")


def _require_string_field(row: SQLiteRowDict, field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Context compaction boundary row is invalid.")
    return value


def _load_completed_context_compaction_tool_row(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    tool_call_id: str,
) -> SQLiteRowDict:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT id, assistant_at_ms, tool_result
            FROM webui_chat_tool_calls
            WHERE conv_id = ?
              AND assistant_turn_at_ms = ?
              AND model_variant_index = ?
              AND call_id = ?
              AND tool_name = ?
              AND status = 'completed'
            LIMIT 1
            """,
            (
                conv_id,
                assistant_turn_at_ms,
                model_variant_index,
                tool_call_id,
                CONTEXT_COMPACTION_TOOL_NAME,
            ),
        ),
    )
    if row is None:
        raise ValidationError("Context compaction boundary was not found.")
    return row


def _resolve_assistant_at_ms(row: SQLiteRowDict) -> int:
    value = row.get("assistant_at_ms")
    if not is_strict_int(value):
        raise ValidationError("Context compaction boundary is not anchored to a message.")
    return int(value)


def _resolve_tool_result(row: SQLiteRowDict) -> JSONDict:
    value = row.get("tool_result")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Context compaction boundary result is invalid.")
    return parse_json_dict(value, field="context compaction tool result")


def _update_matching_assistant_event(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
    tool_call_id: str,
    removed_at_ms: int,
) -> None:
    rows = conn.execute(
        """
        SELECT sequence, payload_json
        FROM webui_assistant_message_events
        WHERE conv_id = ?
          AND assistant_at_ms = ?
          AND event_type = 'tool_call_completed'
        ORDER BY sequence ASC
        """,
        (conv_id, assistant_at_ms),
    ).fetchall()
    for sequence, payload_json in rows:
        if not isinstance(payload_json, str) or not payload_json.strip():
            raise ValidationError("Context compaction boundary event payload is invalid.")
        payload = parse_json_dict(payload_json, field="assistant compaction event payload")
        tool = coerce_json_dict(payload.get("tool"))
        if tool is None:
            continue
        call_id_value = tool.get("call_id")
        tool_name_value = tool.get("tool_name")
        if call_id_value != tool_call_id or tool_name_value != CONTEXT_COMPACTION_TOOL_NAME:
            continue
        event_result = coerce_json_dict(tool.get("result"))
        if event_result is None:
            raise ValidationError("Context compaction boundary event result is invalid.")
        tool["result"] = mark_context_compaction_result_boundary_removed(
            event_result,
            removed_at_ms=removed_at_ms,
            reason=_BOUNDARY_REMOVED_REASON,
        )
        payload["tool"] = build_tool_event_payload_preview(tool)
        conn.execute(
            """
            UPDATE webui_assistant_message_events
            SET payload_json = ?
            WHERE conv_id = ?
              AND assistant_at_ms = ?
              AND sequence = ?
            """,
            (
                serialize_json_compact_stable_strict(payload),
                conv_id,
                assistant_at_ms,
                sequence,
            ),
        )
        return
    raise ValidationError("Context compaction boundary event was not found.")


def sync_remove_context_compaction_boundary(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    tool_call_id: str,
    expected_last_modified_at_ms: int,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    _require_no_running_agent_turn(conn, conv_id=conv_id, user_id=user_id)
    sync_require_expected_conversation_version(
        conn,
        conv_id=conv_id,
        expected_last_modified_at_ms=expected_last_modified_at_ms,
    )
    tool_row = _load_completed_context_compaction_tool_row(
        conn,
        conv_id=conv_id,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        tool_call_id=tool_call_id,
    )
    tool_result = _resolve_tool_result(tool_row)
    if is_context_compaction_result_boundary_removed(tool_result):
        return ConversationMessageWriteResult(
            last_modified_at_ms=sync_load_conversation_last_modified_at_ms(conn, conv_id),
            message_count=sync_count_stored_messages(conn, conv_id),
        )
    removed_at_ms = epoch_ms()
    updated_result = mark_context_compaction_result_boundary_removed(
        tool_result,
        removed_at_ms=removed_at_ms,
        reason=_BOUNDARY_REMOVED_REASON,
    )
    conn.execute(
        "UPDATE webui_chat_tool_calls SET tool_result = ? WHERE id = ?",
        (
            serialize_json_compact_stable_strict(updated_result),
            _require_string_field(tool_row, "id"),
        ),
    )
    _update_matching_assistant_event(
        conn,
        conv_id=conv_id,
        assistant_at_ms=_resolve_assistant_at_ms(tool_row),
        tool_call_id=tool_call_id,
        removed_at_ms=removed_at_ms,
    )
    return ConversationMessageWriteResult(
        last_modified_at_ms=sync_bump_conversation_last_modified_at_ms(conn, conv_id),
        message_count=sync_count_stored_messages(conn, conv_id),
    )
