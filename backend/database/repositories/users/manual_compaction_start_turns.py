"""SoAI - Manual compaction start turn state [backend/database/repositories/users/manual_compaction_start_turns.py]"""
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
from core.errors.exceptions import ValidationError
from core.tool_calls.activity_snapshot_merging import upsert_tool_activity_snapshot
from database.repositories.users.agent_turn_rows import format_agent_turn_row
from database.repositories.users.agent_turn_transactions import load_turn_row
from database.repositories.users.manual_compaction_turn_state_support import (
    build_manual_compaction_running_event,
    build_manual_compaction_tool_calls,
    build_manual_compaction_tool_created_event,
    sync_write_manual_compaction_turn_state,
)

if TYPE_CHECKING:
    from core.database.requests import ManualCompactionStartCommitRequest
    from core.events.types_conversation import (
        ToolCallCreatedEvent,
        ToolCallStartedEvent,
    )
    from core.types.json import JSONDict

__all__ = (
    "build_manual_compaction_start_activity_event",
    "build_manual_compaction_start_todo_state",
    "sync_write_manual_compaction_start_turn",
)


def build_manual_compaction_start_todo_state(turn_record: JSONDict) -> AgentTurnTodoState:
    return AgentTurnTodoState(
        todo=read_turn_payload_entries(turn_record, "todo"),
        todo_explanation=read_turn_optional_text(turn_record, "todo_explanation"),
        todo_revision=read_turn_int(turn_record, "todo_revision") or 0,
        todo_updated_at_ms=None,
    )


def build_manual_compaction_start_activity_event(
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


def sync_write_manual_compaction_start_turn(
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
        event=build_manual_compaction_start_activity_event(
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
        event=build_manual_compaction_start_activity_event(
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
        todo_state=build_manual_compaction_start_todo_state(turn_record),
        started_at_ms=int(assistant_at_ms),
        updated_at_ms=updated_at_ms,
        finished_at_ms=None,
    )
