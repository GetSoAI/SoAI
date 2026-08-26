"""SoAI - Manual compaction turn-state helpers [backend/database/repositories/users/manual_compaction_turn_state_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.todo_state_models import AgentTurnTodoState
from core.agent.turn_state_requests import compose_turn_state_request_from_existing_turn
from core.tool_calls.context_compaction_events import (
    build_context_compaction_tool_call_completed_event,
    build_context_compaction_tool_call_created_event,
    build_context_compaction_tool_call_started_event,
)
from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from database.repositories.users.agent_turn_transactions import sync_write_turn_state

if TYPE_CHECKING:
    from core.database.requests import (
        ManualCompactionStartCommitRequest,
        ManualCompactionTerminalCommitRequest,
    )
    from core.events.types_conversation import (
        ToolCallCompletedEvent,
        ToolCallCreatedEvent,
        ToolCallStartedEvent,
    )
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_manual_compaction_completed_event",
    "build_manual_compaction_running_event",
    "build_manual_compaction_tool_calls",
    "build_manual_compaction_tool_created_event",
    "sync_write_manual_compaction_turn_state",
)


@dataclass(frozen=True, slots=True)
class _ManualCompactionToolEventContext:
    user_id: int
    conv_id: str
    tool_call_id: str
    message_index: int
    turn_id: str
    iteration_index: int


def _build_tool_event_context(
    *,
    user_id: int,
    conv_id: str,
    tool_call_id: str,
    message_index: int,
    turn_id: str,
    iteration_index: int,
) -> _ManualCompactionToolEventContext:
    return _ManualCompactionToolEventContext(
        user_id=int(user_id),
        conv_id=conv_id,
        tool_call_id=tool_call_id,
        message_index=int(message_index),
        turn_id=turn_id,
        iteration_index=int(iteration_index),
    )


def build_manual_compaction_tool_calls(
    *,
    tool_call_id: str,
    tool_started_at_ms: int,
    duration_ms: int,
) -> list[JSONDict]:
    return [
        {
            "id": tool_call_id,
            "name": CONTEXT_COMPACTION_TOOL_NAME,
            "started_at_ms": int(tool_started_at_ms),
            "duration_ms": int(duration_ms),
        },
    ]


def build_manual_compaction_tool_created_event(
    request: ManualCompactionStartCommitRequest,
    *,
    message_index: int,
) -> ToolCallCreatedEvent:
    context = _build_tool_event_context(
        user_id=int(request.user_id),
        conv_id=request.conv_id,
        tool_call_id=request.tool_call_id,
        message_index=message_index,
        turn_id=request.turn_id,
        iteration_index=int(request.iteration_index),
    )
    return build_context_compaction_tool_call_created_event(
        conv_id=context.conv_id,
        user_id=context.user_id,
        turn_id=context.turn_id,
        iteration_index=context.iteration_index,
        call_id=context.tool_call_id,
        message_index=context.message_index,
        sequence_index=0,
        content_index_before=0,
        thinking_index_before=0,
        thinking_duration_before_ms=None,
    )


def build_manual_compaction_running_event(
    request: ManualCompactionStartCommitRequest,
    *,
    assistant_at_ms: int,
    message_index: int,
) -> ToolCallStartedEvent:
    context = _build_tool_event_context(
        user_id=int(request.user_id),
        conv_id=request.conv_id,
        tool_call_id=request.tool_call_id,
        message_index=message_index,
        turn_id=request.turn_id,
        iteration_index=int(request.iteration_index),
    )
    return build_context_compaction_tool_call_started_event(
        conv_id=context.conv_id,
        user_id=context.user_id,
        turn_id=context.turn_id,
        iteration_index=context.iteration_index,
        call_id=context.tool_call_id,
        message_index=context.message_index,
        sequence_index=0,
        content_index_before=0,
        thinking_index_before=0,
        thinking_duration_before_ms=None,
        started_at_ms=int(assistant_at_ms),
    )


def build_manual_compaction_completed_event(
    request: ManualCompactionTerminalCommitRequest,
    *,
    message_index: int,
    duration_ms: int,
    result_payload: JSONValue,
) -> ToolCallCompletedEvent:
    context = _build_tool_event_context(
        user_id=int(request.user_id),
        conv_id=request.conv_id,
        tool_call_id=request.tool_call_id,
        message_index=message_index,
        turn_id=request.turn_id,
        iteration_index=int(request.iteration_index),
    )
    return build_context_compaction_tool_call_completed_event(
        conv_id=context.conv_id,
        user_id=context.user_id,
        turn_id=context.turn_id,
        iteration_index=context.iteration_index,
        call_id=context.tool_call_id,
        message_index=context.message_index,
        sequence_index=0,
        content_index_before=0,
        thinking_index_before=0,
        thinking_duration_before_ms=None,
        status=request.terminal_status,
        result=result_payload,
        duration_ms=int(duration_ms),
        error_message=request.error_message,
    )


def sync_write_manual_compaction_turn_state(
    conn: sqlite3.Connection,
    *,
    existing_turn: JSONDict,
    request: ManualCompactionStartCommitRequest | ManualCompactionTerminalCommitRequest,
    status: str,
    mode: str,
    max_iterations: int,
    iteration_index: int,
    sequence: int,
    tool_calls: list[JSONDict],
    tool_results: list[JSONValue],
    activities: list[JSONDict],
    error_message: str | None,
    error_type: str | None,
    token_usage: JSONDict | None,
    todo_state: AgentTurnTodoState,
    started_at_ms: int,
    updated_at_ms: int,
    finished_at_ms: int | None,
) -> None:
    sync_write_turn_state(
        conn,
        compose_turn_state_request_from_existing_turn(
            existing_turn=existing_turn,
            conv_id=request.conv_id,
            user_id=int(request.user_id),
            turn_id=request.turn_id,
            execution_token=request.execution_token,
            status=status,
            mode=mode,
            max_iterations=max_iterations,
            iteration_index=iteration_index,
            sequence=sequence,
            turn_cancellation_id=request.turn_cancellation_id,
            active_inference_cancellation_id=None,
            assistant_text="",
            tool_calls=tool_calls,
            tool_results=tool_results,
            activities=activities,
            reached_max_iterations=False,
            finished_at_ms=finished_at_ms,
            started_at_ms=started_at_ms,
            updated_at_ms=updated_at_ms,
            todo_state=todo_state,
            token_usage=token_usage,
            error_message=error_message,
            error_type=error_type,
        ),
    )
