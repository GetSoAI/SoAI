"""SoAI - Shared context compaction tool event builders [backend/core/tool_calls/context_compaction_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_conversation import (
    ToolCallCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallStartedEvent,
)
from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "build_context_compaction_tool_call_completed_event",
    "build_context_compaction_tool_call_created_event",
    "build_context_compaction_tool_call_started_event",
)


def build_context_compaction_tool_call_created_event(
    *,
    user_id: int,
    conv_id: str,
    call_id: str,
    message_index: int,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
    thinking_duration_before_ms: int | None,
    turn_id: str | None,
    iteration_index: int,
) -> ToolCallCreatedEvent:
    return ToolCallCreatedEvent(
        user_id=int(user_id),
        conv_id=str(conv_id),
        call_id=str(call_id),
        tool_name=CONTEXT_COMPACTION_TOOL_NAME,
        message_index=int(message_index),
        sequence_index=int(sequence_index),
        content_index_before=int(content_index_before),
        thinking_index_before=int(thinking_index_before),
        thinking_duration_before_ms=thinking_duration_before_ms,
        tool_arguments=None,
        turn_id=turn_id,
        iteration_index=int(iteration_index),
    )


def build_context_compaction_tool_call_started_event(
    *,
    user_id: int,
    conv_id: str,
    call_id: str,
    message_index: int,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
    thinking_duration_before_ms: int | None,
    started_at_ms: int,
    turn_id: str | None,
    iteration_index: int,
) -> ToolCallStartedEvent:
    return ToolCallStartedEvent(
        user_id=int(user_id),
        conv_id=str(conv_id),
        call_id=str(call_id),
        tool_name=CONTEXT_COMPACTION_TOOL_NAME,
        message_index=int(message_index),
        sequence_index=int(sequence_index),
        content_index_before=int(content_index_before),
        thinking_index_before=int(thinking_index_before),
        thinking_duration_before_ms=thinking_duration_before_ms,
        started_at_ms=int(started_at_ms),
        tool_arguments=None,
        turn_id=turn_id,
        iteration_index=int(iteration_index),
    )


def build_context_compaction_tool_call_completed_event(
    *,
    user_id: int,
    conv_id: str,
    call_id: str,
    message_index: int,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
    thinking_duration_before_ms: int | None,
    status: str,
    result: JSONValue,
    duration_ms: int,
    error_message: str | None,
    turn_id: str | None,
    iteration_index: int,
) -> ToolCallCompletedEvent:
    return ToolCallCompletedEvent(
        user_id=int(user_id),
        conv_id=str(conv_id),
        call_id=str(call_id),
        tool_name=CONTEXT_COMPACTION_TOOL_NAME,
        status=str(status),
        message_index=int(message_index),
        sequence_index=int(sequence_index),
        content_index_before=int(content_index_before),
        thinking_index_before=int(thinking_index_before),
        thinking_duration_before_ms=thinking_duration_before_ms,
        tool_arguments=None,
        result=result,
        duration_ms=int(duration_ms),
        error_message=error_message,
        code_diffs=None,
        turn_id=turn_id,
        iteration_index=int(iteration_index),
    )
