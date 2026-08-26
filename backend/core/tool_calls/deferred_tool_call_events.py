"""SoAI - Deferred tool call lifecycle event publishing [backend/core/tool_calls/deferred_tool_call_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_system import (
    ToolCallCompletedEvent,
    ToolCallStartedEvent,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.tool_calls.deferred_tool_call_row import DeferredToolCallRow
    from core.types.json import JSONValue

__all__ = (
    "publish_deferred_tool_call_completed_event",
    "publish_deferred_tool_call_started_event",
)


async def publish_deferred_tool_call_started_event(
    *,
    event_bus: EventBusProtocol,
    row: DeferredToolCallRow,
    call_id: str,
    tool_name: str,
    user_id: int,
    started_at_ms: int,
) -> None:
    await event_bus.publish(
        ToolCallStartedEvent(
            user_id=int(user_id),
            conv_id=row.conv_id,
            call_id=call_id,
            tool_name=tool_name,
            message_index=int(row.message_index),
            sequence_index=int(row.sequence_index),
            content_index_before=int(row.content_index_before),
            thinking_index_before=int(row.thinking_index_before),
            thinking_duration_before_ms=row.thinking_duration_before_ms,
            started_at_ms=started_at_ms,
            tool_arguments=row.tool_arguments_json,
            turn_id=row.turn_id,
            iteration_index=row.iteration_index,
        ),
    )


async def publish_deferred_tool_call_completed_event(
    *,
    event_bus: EventBusProtocol,
    row: DeferredToolCallRow,
    call_id: str,
    tool_name: str,
    user_id: int,
    status: str,
    duration_ms: int,
    error_message: str | None,
    result_payload: JSONValue | None,
) -> None:
    await event_bus.publish(
        ToolCallCompletedEvent(
            user_id=int(user_id),
            conv_id=row.conv_id,
            call_id=call_id,
            tool_name=tool_name,
            status=status,
            message_index=int(row.message_index),
            sequence_index=int(row.sequence_index),
            content_index_before=int(row.content_index_before),
            thinking_index_before=int(row.thinking_index_before),
            thinking_duration_before_ms=row.thinking_duration_before_ms,
            tool_arguments=row.tool_arguments_json,
            result=result_payload,
            duration_ms=max(0, int(duration_ms)),
            error_message=error_message,
            code_diffs=None,
            turn_id=row.turn_id,
            iteration_index=row.iteration_index,
        ),
    )
