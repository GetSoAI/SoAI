"""SoAI - Manual compaction start commit transaction [backend/database/repositories/users/manual_compaction_start_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.agent.todo_state_models import AgentTurnTodoState
from core.agent.turn_record_fields import (
    read_turn_int,
    read_turn_optional_text,
    read_turn_payload_entries,
)
from core.database.requests import (
    ManualCompactionAssistantEventRequest,
    ManualCompactionStartCommitRequest,
    ManualCompactionStartCommitResult,
)
from core.errors.exceptions import ValidationError
from core.tool_calls.activity_snapshot_merging import upsert_tool_activity_snapshot
from database.repositories.users.agent_event_sequence_transactions import (
    sync_reserve_agent_event_sequence_range,
)
from database.repositories.users.agent_turn_rows import format_agent_turn_row
from database.repositories.users.agent_turn_transactions import load_turn_row
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
)
from database.repositories.users.manual_compaction_assistant_events import (
    sync_append_manual_compaction_assistant_event,
)
from database.repositories.users.manual_compaction_message_index import (
    sync_resolve_manual_compaction_message_index,
)
from database.repositories.users.manual_compaction_terminal_targets import (
    sync_prepare_manual_compaction_start_target,
)
from database.repositories.users.manual_compaction_turn_state_support import (
    build_manual_compaction_running_event,
    build_manual_compaction_tool_calls,
    build_manual_compaction_tool_created_event,
    sync_write_manual_compaction_turn_state,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages

if TYPE_CHECKING:
    from core.events.types_conversation import (
        ToolCallCreatedEvent,
        ToolCallStartedEvent,
    )
    from core.types.json import JSONDict

__all__ = ("sync_commit_manual_compaction_start",)


def sync_commit_manual_compaction_start(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
) -> ManualCompactionStartCommitResult:
    ensure_conversation_owned(conn, request.conv_id, int(request.user_id))
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
    _append_start_events(
        conn,
        request,
        assistant_at_ms=assistant_at_ms,
        message_index=message_index,
    )
    _write_start_turn_state(
        conn,
        request,
        assistant_at_ms=assistant_at_ms,
        message_index=message_index,
        tool_created_sequence=tool_created_sequence,
        tool_started_sequence=tool_started_sequence,
    )
    last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, request.conv_id)
    return ManualCompactionStartCommitResult(
        assistant_at_ms=int(assistant_at_ms),
        message_index=int(message_index),
        message_count=sync_count_stored_messages(conn, request.conv_id),
        last_modified_at_ms=int(last_modified_at_ms),
        turn_started_sequence=int(turn_started_sequence),
        tool_created_sequence=int(tool_created_sequence),
        tool_started_sequence=int(tool_started_sequence),
    )


def _append_start_events(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
    *,
    assistant_at_ms: int,
    message_index: int,
) -> None:
    if len(request.assistant_events) != 2:
        raise ValidationError("Manual compaction start commit requires two assistant events.")
    for event in request.assistant_events:
        _append_start_event(
            conn,
            request,
            event,
            assistant_at_ms=assistant_at_ms,
            message_index=message_index,
        )


def _append_start_event(
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


def _write_start_turn_state(
    conn: sqlite3.Connection,
    request: ManualCompactionStartCommitRequest,
    *,
    assistant_at_ms: int,
    message_index: int,
    tool_created_sequence: int,
    tool_started_sequence: int,
) -> None:
    turn_record = format_agent_turn_row(
        load_turn_row(
            conn,
            conv_id=request.conv_id,
            user_id=int(request.user_id),
            turn_id=request.turn_id,
        ),
    )
    if turn_record is None:
        raise ValidationError("Manual compaction turn state is missing.")
    if turn_record.get("execution_token") != request.execution_token:
        raise ValidationError("Agent turn execution token is stale.")
    updated_at_ms = max(
        int(assistant_at_ms),
        read_turn_int(turn_record, "updated_at_ms") or int(assistant_at_ms),
    )
    activities = upsert_tool_activity_snapshot(
        read_turn_payload_entries(turn_record, "activities"),
        event=_build_activity_event(
            request,
            assistant_at_ms=assistant_at_ms,
            message_index=message_index,
            status="pending",
        ),
        activity_sequence=int(tool_created_sequence),
        text_length_before=0,
    )
    activities = upsert_tool_activity_snapshot(
        activities,
        event=_build_activity_event(
            request,
            assistant_at_ms=assistant_at_ms,
            message_index=message_index,
            status="running",
        ),
        activity_sequence=int(tool_started_sequence),
        text_length_before=0,
    )
    sync_write_manual_compaction_turn_state(
        conn,
        existing_turn=turn_record,
        request=request,
        status="running",
        mode=request.mode,
        max_iterations=int(request.max_iterations),
        iteration_index=int(request.iteration_index),
        sequence=int(tool_started_sequence),
        tool_calls=build_manual_compaction_tool_calls(
            tool_call_id=request.tool_call_id,
            tool_started_at_ms=int(assistant_at_ms),
            duration_ms=0,
        ),
        tool_results=[],
        activities=activities,
        error_message=None,
        error_type=None,
        token_usage=None,
        todo_state=_build_todo_state(turn_record),
        started_at_ms=int(assistant_at_ms),
        updated_at_ms=updated_at_ms,
        finished_at_ms=None,
    )


def _build_todo_state(turn_record: JSONDict) -> AgentTurnTodoState:
    todo_explanation = read_turn_optional_text(turn_record, "todo_explanation")
    return AgentTurnTodoState(
        todo=read_turn_payload_entries(turn_record, "todo"),
        todo_explanation=todo_explanation,
        todo_revision=read_turn_int(turn_record, "todo_revision") or 0,
        todo_updated_at_ms=None,
    )


def _build_activity_event(
    request: ManualCompactionStartCommitRequest,
    *,
    assistant_at_ms: int,
    message_index: int,
    status: str,
) -> ToolCallCreatedEvent | ToolCallStartedEvent:
    if status == "running":
        return build_manual_compaction_running_event(
            request,
            assistant_at_ms=int(assistant_at_ms),
            message_index=int(message_index),
        )
    return build_manual_compaction_tool_created_event(request, message_index=int(message_index))
