"""SoAI - Auto-compaction chronology-aware event builders [backend/features/agent/runtime/turn_compaction_activity_event_builders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.context_compaction_events import (
    build_context_compaction_tool_call_completed_event,
    build_context_compaction_tool_call_created_event,
    build_context_compaction_tool_call_started_event,
)

if TYPE_CHECKING:
    from core.events.types_conversation import (
        ToolCallCompletedEvent,
        ToolCallCreatedEvent,
        ToolCallStartedEvent,
    )
    from core.types.json import JSONValue
    from features.agent.runtime.turn_compaction_activity_scope import (
        AutoCompactionActivityScope,
    )
    from features.agent.runtime.turn_compaction_activity_state import (
        AutoCompactionActivityChronology,
    )

__all__ = (
    "build_auto_compaction_completed_event",
    "build_auto_compaction_created_event",
    "build_auto_compaction_started_event",
)


def build_auto_compaction_created_event(
    *,
    scope: AutoCompactionActivityScope,
    call_id: str,
    sequence_index: int,
    chronology: AutoCompactionActivityChronology,
) -> ToolCallCreatedEvent:
    return build_context_compaction_tool_call_created_event(
        user_id=scope.user_id,
        conv_id=scope.conv_id,
        call_id=call_id,
        message_index=scope.message_index,
        sequence_index=sequence_index,
        content_index_before=chronology.content_index_before,
        thinking_index_before=chronology.thinking_index_before,
        thinking_duration_before_ms=chronology.thinking_duration_before_ms,
        turn_id=scope.turn_id,
        iteration_index=scope.iteration_index,
    )


def build_auto_compaction_started_event(
    *,
    scope: AutoCompactionActivityScope,
    call_id: str,
    sequence_index: int,
    chronology: AutoCompactionActivityChronology,
    started_at_ms: int,
) -> ToolCallStartedEvent:
    return build_context_compaction_tool_call_started_event(
        user_id=scope.user_id,
        conv_id=scope.conv_id,
        call_id=call_id,
        message_index=scope.message_index,
        sequence_index=sequence_index,
        content_index_before=chronology.content_index_before,
        thinking_index_before=chronology.thinking_index_before,
        thinking_duration_before_ms=chronology.thinking_duration_before_ms,
        started_at_ms=started_at_ms,
        turn_id=scope.turn_id,
        iteration_index=scope.iteration_index,
    )


def build_auto_compaction_completed_event(
    *,
    scope: AutoCompactionActivityScope,
    call_id: str,
    sequence_index: int,
    chronology: AutoCompactionActivityChronology,
    status: str,
    result: JSONValue,
    duration_ms: int,
    error_message: str | None,
) -> ToolCallCompletedEvent:
    return build_context_compaction_tool_call_completed_event(
        user_id=scope.user_id,
        conv_id=scope.conv_id,
        call_id=call_id,
        message_index=scope.message_index,
        sequence_index=sequence_index,
        content_index_before=chronology.content_index_before,
        thinking_index_before=chronology.thinking_index_before,
        thinking_duration_before_ms=chronology.thinking_duration_before_ms,
        status=status,
        result=result,
        duration_ms=duration_ms,
        error_message=error_message,
        turn_id=scope.turn_id,
        iteration_index=scope.iteration_index,
    )
