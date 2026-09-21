"""SoAI - Manual compaction start commit transaction [backend/database/repositories/users/manual_compaction_start_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.requests import (
    ManualCompactionAssistantEventRequest,
    ManualCompactionStartCommitRequest,
    ManualCompactionStartCommitResult,
)
from core.errors.exceptions import ConflictError, ValidationError
from database.repositories.users.agent_event_sequence_transactions import (
    sync_reserve_agent_event_sequence_range,
)
from database.repositories.users.agent_turn_transactions import sync_claim_turn_state
from database.repositories.users.conversation_input_active_state_reads import (
    sync_read_active_conversation_input_summary,
)
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_stream_cancellation_state import (
    sync_has_pending_chat_stream_cancellation,
)
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
    sync_require_expected_conversation_version,
)
from database.repositories.users.manual_compaction_assistant_events import (
    sync_append_manual_compaction_assistant_event,
)
from database.repositories.users.manual_compaction_message_index import (
    sync_resolve_manual_compaction_message_index,
)
from database.repositories.users.manual_compaction_start_turns import (
    sync_write_manual_compaction_start_turn,
)
from database.repositories.users.manual_compaction_terminal_targets import (
    sync_prepare_manual_compaction_start_target,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages

__all__ = ("sync_commit_manual_compaction_start",)


def _require_matching_turn_claim(request: ManualCompactionStartCommitRequest) -> None:
    turn_state = request.turn_claim.turn_state
    claim_identity = (
        turn_state.conv_id,
        turn_state.user_id,
        turn_state.turn_id,
        turn_state.execution_token,
        turn_state.status,
        turn_state.mode,
        turn_state.max_iterations,
        turn_state.iteration_index,
        turn_state.turn_cancellation_id,
    )
    request_identity = (
        request.conv_id,
        request.user_id,
        request.turn_id,
        request.execution_token,
        "running",
        request.mode,
        request.max_iterations,
        request.iteration_index,
        request.turn_cancellation_id,
    )
    if claim_identity != request_identity:
        raise ValidationError("Manual compaction turn claim does not match its start request.")


def _require_idle_conversation(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
) -> None:
    active_inputs = sync_read_active_conversation_input_summary(
        conn,
        request.conv_id,
        int(request.user_id),
    )
    if active_inputs.has_active_inputs:
        raise ConflictError("Compaction unavailable while conversation input work is active.")
    if sync_has_pending_chat_stream_cancellation(
        conn,
        int(request.user_id),
        request.conv_id,
    ):
        raise ConflictError("Compaction unavailable while cancellation is pending.")
    running_turn = conn.execute(
        """
        SELECT 1 FROM webui_agent_turns
        WHERE conv_id = ? AND user_id = ? AND turn_scope = 'root'
          AND status = 'running' AND turn_id != ?
        LIMIT 1
        """,
        (request.conv_id, int(request.user_id), request.turn_id),
    ).fetchone()
    if running_turn is not None:
        raise ConflictError("Compaction unavailable while agent is running.")


def sync_commit_manual_compaction_start(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
) -> ManualCompactionStartCommitResult:
    ensure_conversation_owned(conn, request.conv_id, int(request.user_id))
    _require_matching_turn_claim(request)
    _require_idle_conversation(conn, request)
    if request.manual_regeneration_request_json is not None:
        if request.manual_regeneration_expected_revision is None:
            raise ValidationError("Manual compaction regeneration revision is required.")
        sync_require_expected_conversation_version(
            conn,
            conv_id=request.conv_id,
            expected_last_modified_at_ms=request.manual_regeneration_expected_revision,
        )
    sync_claim_turn_state(conn, request.turn_claim)
    assistant_at_ms = sync_prepare_manual_compaction_start_target(conn, request)
    message_index = sync_resolve_manual_compaction_message_index(
        conn,
        conv_id=request.conv_id,
        assistant_at_ms=assistant_at_ms,
    )
    turn_started_sequence, tool_started_sequence = sync_reserve_agent_event_sequence_range(
        conn,
        conv_id=request.conv_id,
        user_id=int(request.user_id),
        count=3,
        updated_at_ms=int(assistant_at_ms),
    )
    tool_created_sequence = int(turn_started_sequence) + 1
    append_manual_compaction_start_events(
        conn,
        request,
        assistant_at_ms=assistant_at_ms,
        message_index=message_index,
    )
    sync_write_manual_compaction_start_turn(
        conn,
        request,
        assistant_at_ms=assistant_at_ms,
        message_index=message_index,
        tool_created_sequence=tool_created_sequence,
        tool_started_sequence=tool_started_sequence,
    )
    last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, request.conv_id)
    if request.manual_regeneration_request_json is not None:
        cursor = conn.execute(
            """
            UPDATE webui_agent_turns
               SET manual_regeneration_request_json = ?,
                   manual_regeneration_accepted_revision = ?
             WHERE conv_id = ? AND user_id = ? AND turn_id = ?
               AND execution_token = ? AND status = 'running'
            """,
            (
                request.manual_regeneration_request_json,
                last_modified_at_ms,
                request.conv_id,
                int(request.user_id),
                request.turn_id,
                request.execution_token,
            ),
        )
        if cursor.rowcount != 1:
            raise ValidationError("Manual compaction regeneration turn claim changed.")
    return ManualCompactionStartCommitResult(
        assistant_at_ms=int(assistant_at_ms),
        message_index=int(message_index),
        message_count=sync_count_stored_messages(conn, request.conv_id),
        last_modified_at_ms=int(last_modified_at_ms),
        turn_started_sequence=int(turn_started_sequence),
        tool_created_sequence=int(tool_created_sequence),
        tool_started_sequence=int(tool_started_sequence),
    )


def append_manual_compaction_start_events(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
    *,
    assistant_at_ms: int,
    message_index: int,
) -> None:
    if len(request.assistant_events) != 2:
        raise ValidationError("Manual compaction start commit requires two assistant events.")
    for event in request.assistant_events:
        append_manual_compaction_start_event(
            conn,
            request,
            event,
            assistant_at_ms=assistant_at_ms,
            message_index=message_index,
        )


def append_manual_compaction_start_event(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
    event: ManualCompactionAssistantEventRequest,
    *,
    assistant_at_ms: int,
    message_index: int,
) -> None:
    tool_payload = dict(event.tool_payload)
    tool_payload["message_index"] = int(message_index)
    if str(event.event_type) == "tool_call_started":
        tool_payload["started_at_ms"] = int(assistant_at_ms)
    sync_append_manual_compaction_assistant_event(
        conn,
        conv_id=request.conv_id,
        assistant_at_ms=int(assistant_at_ms),
        event=event,
        tool_payload=tool_payload,
        created_at_ms=int(assistant_at_ms),
    )
