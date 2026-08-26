"""SoAI - Assistant timeline completed tool live update publication [backend/features/assistant_timeline/tool_completed_live_update.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from features.assistant_timeline.tool_live_update_publishing import (
    publish_tool_call_live_update_for_runtime,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("publish_completed_tool_live_update_locked",)


async def publish_completed_tool_live_update_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_tool_calls: DatabaseToolCallsProtocol,
    call_id: str,
    tool_payload: JSONDict,
) -> None:
    status_value = tool_payload.get("status")
    status = status_value.strip() if isinstance(status_value, str) else "completed"
    duration_value = tool_payload.get("duration_ms")
    duration_ms = duration_value if is_strict_int(duration_value) else None
    completed_at_ms = tool_payload.get("completed_at_ms")
    completed_timestamp = completed_at_ms if is_strict_int(completed_at_ms) else epoch_ms()
    error_value = tool_payload.get("error")
    error_message = (
        error_value.strip()
        if status in {"cancelled", "error"} and isinstance(error_value, str)
        else None
    )
    if status in {"cancelled", "error"} and error_message is None:
        error_message = "Tool call finished without an error message."
    await publish_tool_call_live_update_for_runtime(
        event_bus=event_bus,
        database_tool_calls=database_tool_calls,
        runtime=runtime,
        call_id=call_id,
        event_type="tool_call_completed",
        tool_payload=tool_payload,
        status=status,
        duration_ms=duration_ms,
        started_at_ms=None,
        tool_result=tool_payload.get("result"),
        error_message=error_message,
        completed_at_ms=completed_timestamp,
    )
