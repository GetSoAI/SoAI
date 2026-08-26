"""SoAI - Manual compaction terminal turn rows [backend/database/repositories/users/manual_compaction_terminal_turns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.agent.todo_state_models import AgentTurnTodoState
from core.agent.turn_record_fields import read_turn_payload_entries
from core.assistant_timeline.tool_result_truncation import (
    truncate_tool_result_payload_for_timeline,
)
from core.database.requests import ManualCompactionTerminalCommitRequest
from core.errors.exceptions import ValidationError
from core.tool_calls.activity_snapshot_merging import upsert_tool_activity_snapshot
from core.tool_calls.status_values import TOOL_CALL_TERMINAL_STATUSES
from core.validation.integers import is_strict_int
from database.repositories.users.agent_turn_rows import format_agent_turn_row
from database.repositories.users.agent_turn_transactions import load_turn_row
from database.repositories.users.manual_compaction_turn_state_support import (
    build_manual_compaction_completed_event,
    build_manual_compaction_tool_calls,
    sync_write_manual_compaction_turn_state,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_commit_manual_compaction_turn_state",)


def sync_commit_manual_compaction_turn_state(
    conn: sqlite3.Connection,
    request: ManualCompactionTerminalCommitRequest,
    *,
    message_index: int,
    tool_completion_sequence: int,
    turn_terminal_sequence: int,
) -> None:
    if request.terminal_status not in TOOL_CALL_TERMINAL_STATUSES:
        raise ValidationError("Manual compaction terminal status is invalid.")
    turn_record = _load_running_turn_record(conn, request)
    started_at_ms = _read_required_turn_int(turn_record, "started_at_ms")
    completed_at_ms = max(int(request.completed_at_ms), started_at_ms)
    duration_ms = max(0, completed_at_ms - int(request.tool_started_at_ms))
    sync_write_manual_compaction_turn_state(
        conn,
        existing_turn=turn_record,
        request=request,
        status=request.terminal_status,
        mode=_read_required_turn_text(turn_record, "mode"),
        max_iterations=_read_required_turn_int(turn_record, "max_iterations"),
        iteration_index=int(request.iteration_index),
        sequence=int(turn_terminal_sequence),
        tool_calls=build_manual_compaction_tool_calls(
            tool_call_id=request.tool_call_id,
            tool_started_at_ms=int(request.tool_started_at_ms),
            duration_ms=duration_ms,
        ),
        tool_results=[request.result_payload],
        activities=_build_activities(
            request,
            turn_record=turn_record,
            message_index=message_index,
            duration_ms=duration_ms,
            tool_completion_sequence=tool_completion_sequence,
        ),
        error_message=request.error_message,
        error_type=request.error_type,
        token_usage=_read_optional_turn_dict(turn_record, "token_usage"),
        todo_state=_build_todo_state(turn_record),
        started_at_ms=started_at_ms,
        updated_at_ms=completed_at_ms,
        finished_at_ms=completed_at_ms,
    )


def _load_running_turn_record(
    conn: sqlite3.Connection,
    request: ManualCompactionTerminalCommitRequest,
) -> JSONDict:
    turn_row = load_turn_row(
        conn,
        conv_id=request.conv_id,
        user_id=int(request.user_id),
        turn_id=request.turn_id,
    )
    turn_record = format_agent_turn_row(turn_row)
    if turn_record is None:
        raise ValidationError("Manual compaction turn state is missing.")
    if turn_record.get("status") != "running":
        raise ValidationError("Manual compaction turn is already terminal.")
    if turn_record.get("execution_token") != request.execution_token:
        raise ValidationError("Agent turn execution token is stale.")
    return turn_record


def _build_activities(
    request: ManualCompactionTerminalCommitRequest,
    *,
    turn_record: JSONDict,
    message_index: int,
    duration_ms: int,
    tool_completion_sequence: int,
) -> list[JSONDict]:
    return upsert_tool_activity_snapshot(
        read_turn_payload_entries(turn_record, "activities"),
        event=build_manual_compaction_completed_event(
            request,
            message_index=int(message_index),
            duration_ms=int(duration_ms),
            result_payload=truncate_tool_result_payload_for_timeline(request.result_payload),
        ),
        activity_sequence=int(tool_completion_sequence),
        text_length_before=0,
    )


def _build_todo_state(turn_record: JSONDict) -> AgentTurnTodoState:
    todo_explanation = turn_record.get("todo_explanation")
    return AgentTurnTodoState(
        todo=read_turn_payload_entries(turn_record, "todo"),
        todo_explanation=todo_explanation if isinstance(todo_explanation, str) else None,
        todo_revision=_read_required_turn_int(turn_record, "todo_revision"),
        todo_updated_at_ms=None,
    )


def _read_required_turn_int(turn_record: JSONDict, field_name: str) -> int:
    value = turn_record.get(field_name)
    if not is_strict_int(value):
        raise ValidationError("Manual compaction turn state is invalid.")
    return int(value)


def _read_required_turn_text(turn_record: JSONDict, field_name: str) -> str:
    value = turn_record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Manual compaction turn state is invalid.")
    return value.strip()


def _read_optional_turn_dict(turn_record: JSONDict, field_name: str) -> JSONDict | None:
    value = turn_record.get(field_name)
    return dict(value) if isinstance(value, dict) else None
