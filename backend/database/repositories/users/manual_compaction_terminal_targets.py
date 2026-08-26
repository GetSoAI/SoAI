"""SoAI - Manual compaction terminal assistant targets [backend/database/repositories/users/manual_compaction_terminal_targets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.requests import (
    ManualCompactionStartCommitRequest,
    ManualCompactionTerminalCommitRequest,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_TOOL_NAME,
    is_context_compaction_result_boundary_removed,
)
from core.types.json_value import coerce_json_dict
from database.repositories.users.message_content_integrity import (
    build_message_content_integrity,
)
from database.repositories.users.tool_call_deletion_transactions import (
    sync_delete_tool_calls_for_assistant_turn_rows,
)

__all__ = (
    "sync_prepare_manual_compaction_start_target",
    "sync_resolve_manual_compaction_assistant_target",
)


def sync_prepare_manual_compaction_start_target(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
) -> int:
    if request.replace_assistant_at_ms is not None:
        assistant_at_ms = int(request.replace_assistant_at_ms)
        _prepare_replacement_target(conn, request, assistant_at_ms=assistant_at_ms)
        return assistant_at_ms
    latest_row = conn.execute(
        """
        SELECT created_at_ms
        FROM webui_messages
        WHERE conv_id = ?
        ORDER BY created_at_ms DESC, id DESC
        LIMIT 1
        """,
        (request.conv_id,),
    ).fetchone()
    latest_timestamp = int(latest_row[0]) if latest_row is not None else 0
    assistant_at_ms = max(int(request.requested_started_at_ms), latest_timestamp + 1)
    _write_unfinished_assistant_row(
        conn,
        request,
        assistant_at_ms=assistant_at_ms,
        insert_row=True,
    )
    return int(assistant_at_ms)


def sync_resolve_manual_compaction_assistant_target(
    conn: sqlite3.Connection,
    request: ManualCompactionTerminalCommitRequest,
) -> int:
    assistant_at_ms = int(request.assistant_at_ms)
    _require_unfinished_canonical_assistant_row(conn, request, assistant_at_ms)
    return int(assistant_at_ms)


def _prepare_replacement_target(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
    *,
    assistant_at_ms: int,
) -> None:
    tool_call_id = str(request.replace_tool_call_id or "").strip()
    if assistant_at_ms <= 0 or not tool_call_id:
        raise ValidationError("Compaction replacement requires a target assistant and tool call.")
    _require_canonical_assistant_row(conn, request, assistant_at_ms)
    _validate_replacement_tool_row(conn, request, assistant_at_ms, tool_call_id)
    _validate_replacement_timeline_event(conn, request, assistant_at_ms, tool_call_id)
    sync_delete_tool_calls_for_assistant_turn_rows(
        conn,
        conv_id=request.conv_id,
        assistant_turn_at_ms=assistant_at_ms,
        model_variant_index=0,
    )
    conn.execute(
        "DELETE FROM webui_assistant_message_events WHERE conv_id = ? AND assistant_at_ms = ?",
        (request.conv_id, assistant_at_ms),
    )
    _write_unfinished_assistant_row(
        conn,
        request,
        assistant_at_ms=assistant_at_ms,
        insert_row=False,
    )


def _write_unfinished_assistant_row(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
    *,
    assistant_at_ms: int,
    insert_row: bool,
) -> None:
    content_json = serialize_json_compact_stable_strict("")
    content_length, content_sha256 = build_message_content_integrity(content_json)
    if insert_row:
        conn.execute(
            """
            INSERT INTO webui_messages (
                conv_id, role, content, content_length, content_sha256, finalized_at_ms,
                created_at_ms, assistant_turn_at_ms, model_variant_index, request_id,
                model_id, prompt_tokens, completion_tokens, total_tokens, usage_source,
                generation_latency_ms, finish_reason, thinking_tail_duration_ms
            ) VALUES (
                ?, 'assistant', ?, ?, ?, NULL, ?, ?, 0, NULL, ?, NULL, NULL, NULL,
                NULL, NULL, NULL, NULL
            )
            """,
            (
                request.conv_id,
                content_json,
                content_length,
                content_sha256,
                int(assistant_at_ms),
                int(assistant_at_ms),
                request.model_id,
            ),
        )
        return
    conn.execute(
        """
        UPDATE webui_messages
        SET content = ?,
            content_length = ?,
            content_sha256 = ?,
            finalized_at_ms = NULL,
            request_id = NULL,
            model_id = ?,
            prompt_tokens = NULL,
            completion_tokens = NULL,
            total_tokens = NULL,
            usage_source = NULL,
            generation_latency_ms = NULL,
            finish_reason = NULL,
            thinking_tail_duration_ms = NULL
        WHERE conv_id = ?
          AND created_at_ms = ?
          AND assistant_turn_at_ms = ?
          AND model_variant_index = 0
          AND role = 'assistant'
        """,
        (
            content_json,
            content_length,
            content_sha256,
            request.model_id,
            request.conv_id,
            int(assistant_at_ms),
            int(assistant_at_ms),
        ),
    )


def _require_canonical_assistant_row(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest | ManualCompactionTerminalCommitRequest,
    assistant_at_ms: int,
) -> None:
    row = conn.execute(
        """
        SELECT 1
        FROM webui_messages
        WHERE conv_id = ?
          AND created_at_ms = ?
          AND assistant_turn_at_ms = ?
          AND model_variant_index = 0
          AND role = 'assistant'
        LIMIT 1
        """,
        (request.conv_id, int(assistant_at_ms), int(assistant_at_ms)),
    ).fetchone()
    if row is None:
        raise ValidationError("Compaction assistant message target could not be resolved.")


def _require_unfinished_canonical_assistant_row(
    conn: sqlite3.Connection,
    request: ManualCompactionTerminalCommitRequest,
    assistant_at_ms: int,
) -> None:
    row = conn.execute(
        """
        SELECT 1
        FROM webui_messages
        WHERE conv_id = ?
          AND created_at_ms = ?
          AND assistant_turn_at_ms = ?
          AND model_variant_index = 0
          AND role = 'assistant'
          AND finalized_at_ms IS NULL
        LIMIT 1
        """,
        (request.conv_id, int(assistant_at_ms), int(assistant_at_ms)),
    ).fetchone()
    if row is None:
        raise ValidationError("Manual compaction activity message is not running.")


def _validate_replacement_tool_row(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
    assistant_at_ms: int,
    tool_call_id: str,
) -> None:
    row = conn.execute(
        """
        SELECT tool_result
        FROM webui_chat_tool_calls
        WHERE conv_id = ?
          AND assistant_turn_at_ms = ?
          AND model_variant_index = 0
          AND call_id = ?
          AND tool_name = ?
          AND status = 'completed'
        LIMIT 1
        """,
        (request.conv_id, int(assistant_at_ms), tool_call_id, CONTEXT_COMPACTION_TOOL_NAME),
    ).fetchone()
    if row is None:
        raise ValidationError("Compaction assistant message target changed before replacement.")
    result_value = row[0]
    if not isinstance(result_value, str) or not result_value.strip():
        raise ValidationError("Compaction assistant message target result is invalid.")
    result_payload = parse_json_dict(result_value, field="context compaction tool result")
    if is_context_compaction_result_boundary_removed(result_payload):
        raise ValidationError("Removed context compaction boundaries cannot be regenerated.")


def _validate_replacement_timeline_event(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
    assistant_at_ms: int,
    tool_call_id: str,
) -> None:
    rows = conn.execute(
        """
        SELECT payload_json
        FROM webui_assistant_message_events
        WHERE conv_id = ?
          AND assistant_at_ms = ?
          AND event_type = 'tool_call_completed'
        """,
        (request.conv_id, int(assistant_at_ms)),
    ).fetchall()
    for (payload_json,) in rows:
        payload = parse_json_dict(payload_json, field="assistant compaction event payload")
        tool = coerce_json_dict(payload.get("tool"))
        if tool is None:
            continue
        if (
            tool.get("call_id") == tool_call_id
            and tool.get("tool_name") == CONTEXT_COMPACTION_TOOL_NAME
        ):
            return
    raise ValidationError("Compaction assistant message target changed before replacement.")
