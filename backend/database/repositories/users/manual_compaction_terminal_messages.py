"""SoAI - Manual compaction terminal message rows [backend/database/repositories/users/manual_compaction_terminal_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.requests import (
    CreateToolCallRequest,
    ManualCompactionTerminalCommitRequest,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_TOOL_NAME,
)
from database.repositories.users.manual_compaction_assistant_events import (
    sync_append_manual_compaction_assistant_event,
)
from database.repositories.users.manual_compaction_message_index import (
    sync_resolve_manual_compaction_message_index,
)
from database.repositories.users.manual_compaction_terminal_targets import (
    sync_resolve_manual_compaction_assistant_target,
)
from database.repositories.users.message_content_integrity import (
    build_message_content_integrity,
)
from database.repositories.users.message_streaming_assistant.terminal_event_normalization import (
    sync_normalize_terminal_assistant_events,
)
from database.repositories.users.tool_call_insert_transactions import (
    sync_create_tool_call,
)

__all__ = ("sync_commit_manual_compaction_message_rows",)


def sync_commit_manual_compaction_message_rows(
    conn: sqlite3.Connection,
    request: ManualCompactionTerminalCommitRequest,
) -> tuple[int, int]:
    assistant_at_ms = sync_resolve_manual_compaction_assistant_target(conn, request)
    message_index = sync_resolve_manual_compaction_message_index(
        conn,
        conv_id=request.conv_id,
        assistant_at_ms=assistant_at_ms,
    )
    _insert_terminal_tool_call(
        conn,
        request,
        assistant_at_ms=assistant_at_ms,
        message_index=message_index,
    )
    _append_completion_event(
        conn,
        request,
        assistant_at_ms=assistant_at_ms,
        message_index=message_index,
    )
    _finalize_assistant_message(conn, request, assistant_at_ms=assistant_at_ms)
    return assistant_at_ms, message_index


def _insert_terminal_tool_call(
    conn: sqlite3.Connection,
    request: ManualCompactionTerminalCommitRequest,
    *,
    assistant_at_ms: int,
    message_index: int,
) -> None:
    duration_ms = max(0, int(request.completed_at_ms) - int(request.tool_started_at_ms))
    sync_create_tool_call(
        conn,
        CreateToolCallRequest(
            call_id=request.tool_call_id,
            storage_call_id=request.tool_call_id,
            conv_id=request.conv_id,
            turn_id=request.turn_id,
            iteration_index=int(request.iteration_index),
            message_index=int(message_index),
            assistant_turn_at_ms=int(assistant_at_ms),
            model_variant_index=0,
            assistant_at_ms=int(assistant_at_ms),
            tool_name=CONTEXT_COMPACTION_TOOL_NAME,
            tool_arguments=None,
            status=request.terminal_status,
            sequence_index=0,
            content_index_before=0,
            thinking_index_before=0,
            thinking_duration_before_ms=None,
            collapsed=True,
            error_message=request.error_message,
            tool_result=serialize_json_compact_stable_strict(request.result_payload),
            duration_ms=duration_ms,
            created_at_ms=int(request.tool_started_at_ms),
            started_at_ms=int(request.tool_started_at_ms),
            completed_at_ms=int(request.completed_at_ms),
        ),
    )


def _append_completion_event(
    conn: sqlite3.Connection,
    request: ManualCompactionTerminalCommitRequest,
    *,
    assistant_at_ms: int,
    message_index: int,
) -> None:
    event = request.terminal_event
    tool_payload = dict(event.tool_payload)
    tool_payload["message_index"] = int(message_index)
    sync_append_manual_compaction_assistant_event(
        conn,
        conv_id=request.conv_id,
        assistant_at_ms=int(assistant_at_ms),
        event=event,
        tool_payload=tool_payload,
        created_at_ms=int(event.created_at_ms),
    )


def _finalize_assistant_message(
    conn: sqlite3.Connection,
    request: ManualCompactionTerminalCommitRequest,
    *,
    assistant_at_ms: int,
) -> None:
    content_json = serialize_json_compact_stable_strict("")
    content_length, content_sha256 = build_message_content_integrity(content_json)
    sync_normalize_terminal_assistant_events(
        conn,
        conv_id=request.conv_id,
        assistant_at_ms=int(assistant_at_ms),
        finish_reason=request.finish_reason,
        terminal_reason=request.error_type,
    )
    cursor = conn.execute(
        """
        UPDATE webui_messages
        SET content_length = ?,
            content_sha256 = ?,
            finalized_at_ms = ?,
            finish_reason = ?
        WHERE conv_id = ?
          AND created_at_ms = ?
          AND role = 'assistant'
          AND finalized_at_ms IS NULL
        """,
        (
            content_length,
            content_sha256,
            int(request.completed_at_ms),
            request.finish_reason,
            request.conv_id,
            int(assistant_at_ms),
        ),
    )
    if cursor.rowcount <= 0:
        raise ValidationError("Streaming assistant message not found.")
