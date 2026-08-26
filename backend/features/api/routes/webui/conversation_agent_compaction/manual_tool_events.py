"""SoAI - Manual compaction tool event builders [backend/features/api/routes/webui/conversation_agent_compaction/manual_tool_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.context_compaction_events import (
    build_context_compaction_tool_call_completed_event,
    build_context_compaction_tool_call_created_event,
    build_context_compaction_tool_call_started_event,
)
from features.api.routes.webui.conversation_agent_compaction.internal_protocols import (
    ManualCompactionStartStateProtocol,
)

if TYPE_CHECKING:
    from core.events.types_conversation import (
        ToolCallCompletedEvent,
        ToolCallCreatedEvent,
        ToolCallStartedEvent,
    )
    from core.types.json import JSONValue

__all__ = (
    "build_manual_compaction_tool_completed_event",
    "build_manual_compaction_tool_created_event",
    "build_manual_compaction_tool_created_event_for_values",
    "build_manual_compaction_tool_started_event",
    "build_manual_compaction_tool_started_event_for_values",
)


def build_manual_compaction_tool_created_event(
    *,
    user_id: int,
    start_state: ManualCompactionStartStateProtocol,
    message_index: int | None = None,
    sequence_index: int = 0,
) -> ToolCallCreatedEvent:
    return build_manual_compaction_tool_created_event_for_values(
        user_id=user_id,
        conv_id=start_state.conv_id,
        call_id=start_state.tool_call_id,
        message_index=start_state.message_index if message_index is None else int(message_index),
        sequence_index=int(sequence_index),
        turn_id=start_state.turn_id,
        iteration_index=int(start_state.iteration_index),
    )


def build_manual_compaction_tool_created_event_for_values(
    *,
    user_id: int,
    conv_id: str,
    call_id: str,
    message_index: int,
    turn_id: str | None,
    iteration_index: int,
    sequence_index: int = 0,
) -> ToolCallCreatedEvent:
    return build_context_compaction_tool_call_created_event(
        user_id=int(user_id),
        conv_id=str(conv_id),
        call_id=str(call_id),
        message_index=int(message_index),
        sequence_index=int(sequence_index),
        content_index_before=0,
        thinking_index_before=0,
        thinking_duration_before_ms=None,
        turn_id=turn_id,
        iteration_index=int(iteration_index),
    )


def build_manual_compaction_tool_started_event(
    *,
    user_id: int,
    start_state: ManualCompactionStartStateProtocol,
    started_at_ms: int,
    message_index: int | None = None,
    sequence_index: int = 0,
) -> ToolCallStartedEvent:
    return build_manual_compaction_tool_started_event_for_values(
        user_id=user_id,
        conv_id=start_state.conv_id,
        call_id=start_state.tool_call_id,
        message_index=start_state.message_index if message_index is None else int(message_index),
        sequence_index=int(sequence_index),
        started_at_ms=started_at_ms,
        turn_id=start_state.turn_id,
        iteration_index=int(start_state.iteration_index),
    )


def build_manual_compaction_tool_started_event_for_values(
    *,
    user_id: int,
    conv_id: str,
    call_id: str,
    message_index: int,
    started_at_ms: int,
    turn_id: str | None,
    iteration_index: int,
    sequence_index: int = 0,
) -> ToolCallStartedEvent:
    return build_context_compaction_tool_call_started_event(
        user_id=int(user_id),
        conv_id=str(conv_id),
        call_id=str(call_id),
        message_index=int(message_index),
        sequence_index=int(sequence_index),
        content_index_before=0,
        thinking_index_before=0,
        thinking_duration_before_ms=None,
        started_at_ms=started_at_ms,
        turn_id=turn_id,
        iteration_index=int(iteration_index),
    )


def build_manual_compaction_tool_completed_event(
    *,
    user_id: int,
    conv_id: str,
    call_id: str,
    message_index: int,
    status: str,
    result: JSONValue,
    duration_ms: int,
    error_message: str | None,
    turn_id: str | None,
    iteration_index: int,
    sequence_index: int = 0,
) -> ToolCallCompletedEvent:
    return build_context_compaction_tool_call_completed_event(
        user_id=int(user_id),
        conv_id=str(conv_id),
        call_id=str(call_id),
        message_index=int(message_index),
        sequence_index=int(sequence_index),
        content_index_before=0,
        thinking_index_before=0,
        thinking_duration_before_ms=None,
        status=status,
        result=result,
        duration_ms=int(duration_ms),
        error_message=error_message,
        turn_id=turn_id,
        iteration_index=int(iteration_index),
    )
