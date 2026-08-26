"""SoAI - Auto-compaction activity projection mapping [backend/features/agent/runtime/turn_compaction_activity_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_calls.visibility import should_persist_visible_tool_call_rows
from features.agent.runtime.context_compaction.tool_projection_persistence import (
    persist_context_compaction_pending_projection,
    persist_context_compaction_started_projection,
)

if TYPE_CHECKING:
    from core.events.types_conversation import ToolCallStartedEvent
    from features.agent.runtime.turn_compaction_activity_scope import (
        AutoCompactionActivityScope,
    )
    from features.agent.runtime.turn_compaction_activity_state import (
        AutoCompactionActivityChronology,
    )

__all__ = (
    "persist_auto_compaction_pending_projection",
    "persist_auto_compaction_started_activity",
)


async def persist_auto_compaction_pending_projection(
    *,
    scope: AutoCompactionActivityScope,
    call_id: str,
    sequence_index: int,
    chronology: AutoCompactionActivityChronology,
    created_at_ms: int,
) -> bool:
    if not should_persist_visible_tool_call_rows(scope.request_context):
        return False
    await persist_context_compaction_pending_projection(
        database_tool_calls=scope.database_tool_calls,
        request_context=scope.request_context,
        tool_context=scope.tool_context,
        call_id=call_id,
        sequence_index=sequence_index,
        content_index_before=chronology.content_index_before,
        thinking_index_before=chronology.thinking_index_before,
        thinking_duration_before_ms=chronology.thinking_duration_before_ms,
        created_at_ms=created_at_ms,
    )
    return True


async def persist_auto_compaction_started_activity(
    *,
    scope: AutoCompactionActivityScope,
    event: ToolCallStartedEvent,
) -> None:
    if event.started_at_ms is None:
        raise ValidationError("Auto-compaction started event is missing started_at_ms.")
    if should_persist_visible_tool_call_rows(scope.request_context):
        await persist_context_compaction_started_projection(
            database_tool_calls=scope.database_tool_calls,
            request_context=scope.request_context,
            tool_context=scope.tool_context,
            call_id=event.call_id,
            sequence_index=event.sequence_index,
            content_index_before=event.content_index_before,
            thinking_index_before=event.thinking_index_before,
            thinking_duration_before_ms=event.thinking_duration_before_ms,
            started_at_ms=event.started_at_ms,
        )
    activity_sequence = int(await scope.next_action_sequence())
    await scope.turn_state_writer.persist_tool_activity(
        event=event,
        activity_sequence=activity_sequence,
        text_length_before=event.content_index_before,
    )
    await scope.publish_event(event)
