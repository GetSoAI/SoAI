"""SoAI - Assistant timeline tool call live update publishing [backend/features/assistant_timeline/tool_live_update_publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.live_update_identity import ToolCallLiveUpdateIdentity
from core.tool_calls.live_update_publishing import publish_tool_call_live_update
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.events.types_system import ToolCallLiveUpdatedEvent
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("publish_tool_call_live_update_for_runtime",)


async def publish_tool_call_live_update_for_runtime(
    *,
    event_bus: EventBusProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    runtime: AssistantTimelineRuntime,
    call_id: str,
    event_type: str,
    tool_payload: JSONDict,
    status: str,
    duration_ms: int | None,
    started_at_ms: int | None,
    tool_result: JSONValue | None,
    error_message: str | None = None,
    completed_at_ms: int | None = None,
) -> ToolCallLiveUpdatedEvent:
    return await publish_tool_call_live_update(
        event_bus=event_bus,
        database_tool_calls=database_tool_calls,
        identity=ToolCallLiveUpdateIdentity(
            user_id=runtime.user_id,
            conv_id=runtime.conv_id,
            request_id=runtime.request_id,
            assistant_at_ms=runtime.assistant_at_ms,
            assistant_turn_at_ms=runtime.assistant_turn_at_ms,
            model_variant_index=runtime.model_variant_index,
        ),
        call_id=call_id,
        event_type=event_type,
        tool_payload=tool_payload,
        status=status,
        duration_ms=duration_ms,
        started_at_ms=started_at_ms,
        tool_result=tool_result,
        error_message=error_message,
        completed_at_ms=completed_at_ms,
    )
