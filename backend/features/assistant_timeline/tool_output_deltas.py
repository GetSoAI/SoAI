"""SoAI - Shared assistant timeline tool output delta handling [backend/features/assistant_timeline/tool_output_deltas.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.timing.monotonic import monotonic_ms
from core.tool_calls.status_values import TOOL_CALL_STATUS_RUNNING
from features.assistant_timeline.post_terminal_tool_events import (
    runtime_requires_post_terminal_tool_projection,
)
from features.assistant_timeline.runtime_matching import (
    matches_assistant_timeline_runtime,
)
from features.assistant_timeline.tool_events_flushing import (
    flush_pending_tool_output_deltas_for_call_id_locked,
)
from features.assistant_timeline.tool_live_update_publishing import (
    publish_tool_call_live_update_for_runtime,
)
from features.assistant_timeline.tool_output_delta_drain import (
    drain_pending_tool_output_deltas_locked,
)
from features.assistant_timeline.tool_payload_state import (
    build_latest_tool_update_payload,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.events.types_system import ToolCallOutputDeltaEvent
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "handle_tool_output_delta_event_locked",
    "matches_output_delta_runtime",
)

_TOOL_OUTPUT_FLUSH_MIN_INTERVAL_MS: int = 250


def _append_tool_output_delta_locked(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
    delta: str,
) -> None:
    normalized_call_id = call_id.strip()
    if not normalized_call_id:
        return
    if not delta:
        return
    pending = runtime.pending_tool_output_deltas_by_call_id.get(normalized_call_id)
    if pending is None:
        runtime.pending_tool_output_deltas_by_call_id[normalized_call_id] = [delta]
        return
    if pending and len(pending[-1]) < 8192 and len(delta) < 8192:
        pending[-1] = pending[-1] + delta
        return
    pending.append(delta)


async def _publish_post_terminal_tool_output_delta_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_tool_calls: DatabaseToolCallsProtocol,
    call_id: str,
) -> None:
    drain_result = drain_pending_tool_output_deltas_locked(
        runtime=runtime,
        call_id=call_id,
    )
    if drain_result is None or not drain_result.has_output:
        return
    tool_payload = build_latest_tool_update_payload(
        runtime=runtime,
        call_id=call_id,
        result=drain_result.tool_result,
    )
    if tool_payload is None:
        raise StateError("Post-terminal tool output update missing canonical tool payload state.")
    await publish_tool_call_live_update_for_runtime(
        event_bus=event_bus,
        database_tool_calls=database_tool_calls,
        runtime=runtime,
        call_id=call_id,
        event_type="tool_call_updated",
        tool_payload=tool_payload,
        status=TOOL_CALL_STATUS_RUNNING,
        duration_ms=None,
        started_at_ms=runtime.tool_call_started_at_ms_by_call_id.get(call_id),
        tool_result=drain_result.tool_result,
    )


def matches_output_delta_runtime(
    *,
    runtime: AssistantTimelineRuntime,
    event: ToolCallOutputDeltaEvent,
) -> bool:
    return matches_assistant_timeline_runtime(
        runtime=runtime,
        event_user_id=event.user_id,
        event_conv_id=event.conv_id,
        event_message_index=event.message_index,
        event_turn_id=event.turn_id,
    )


async def handle_tool_output_delta_event_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    event: ToolCallOutputDeltaEvent,
) -> None:
    if not matches_output_delta_runtime(runtime=runtime, event=event):
        return
    call_id = event.call_id.strip()
    if not call_id or call_id in runtime.completed_tool_call_ids:
        return
    tool_name = event.tool_name.strip()
    if tool_name:
        runtime.tool_name_by_call_id[call_id] = tool_name
    delta = event.delta
    if not delta:
        return
    _append_tool_output_delta_locked(runtime=runtime, call_id=call_id, delta=delta)
    if runtime_requires_post_terminal_tool_projection(runtime):
        if call_id in runtime.emitted_tool_call_started_ids:
            await _publish_post_terminal_tool_output_delta_locked(
                event_bus=event_bus,
                runtime=runtime,
                database_tool_calls=database_tool_calls,
                call_id=call_id,
            )
        return
    if call_id in runtime.emitted_tool_call_started_ids:
        now_ms = monotonic_ms()
        last_flush_ms = runtime.tool_output_delta_last_flush_monotonic_ms_by_call_id.get(call_id, 0)
        if now_ms - last_flush_ms >= _TOOL_OUTPUT_FLUSH_MIN_INTERVAL_MS:
            await flush_pending_tool_output_deltas_for_call_id_locked(
                event_bus=event_bus,
                runtime=runtime,
                database_messages=database_messages,
                database_tool_calls=database_tool_calls,
                call_id=call_id,
            )
            runtime.tool_output_delta_last_flush_monotonic_ms_by_call_id[call_id] = int(now_ms)
