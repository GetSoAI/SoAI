"""SoAI - Shared assistant timeline tool event flushing [backend/features/assistant_timeline/tool_events_flushing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.assistant_timeline.tool_event_payload_contract import (
    build_tool_event_payload_preview,
)
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tool_calls.status_values import TOOL_CALL_STATUS_RUNNING
from features.assistant_timeline.models import (
    AssistantTimelineRuntime,
    PendingToolEvent,
)
from features.assistant_timeline.publish import (
    ensure_chat_stream_publish_lock,
)
from features.assistant_timeline.tool_call_projection_persistence import (
    persist_tool_call_created_projection,
)
from features.assistant_timeline.tool_completed_live_update import (
    publish_completed_tool_live_update_locked,
)
from features.assistant_timeline.tool_event_layout import (
    cache_tool_call_layout_from_payload,
)
from features.assistant_timeline.tool_events_state import (
    record_tool_call_completed_locked,
    record_tool_call_started_locked,
)
from features.assistant_timeline.tool_live_update_publishing import (
    publish_tool_call_live_update_for_runtime,
)
from features.assistant_timeline.tool_output_delta_drain import (
    drain_pending_tool_output_deltas_locked,
)
from features.assistant_timeline.tool_payload_state import (
    build_latest_tool_update_payload,
    record_latest_tool_payload_locked,
)
from features.assistant_timeline.visible_activity_event_emission import (
    complete_processing_activity_and_publish_visible_event_locked,
    flush_assistant_text_for_visible_events_locked,
    normalize_tool_payload_content_anchor_locked,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = (
    "flush_pending_tool_events",
    "flush_pending_tool_events_locked",
    "flush_pending_tool_output_deltas_for_call_id_locked",
)


async def flush_pending_tool_output_deltas_for_call_id_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    call_id: str,
) -> None:
    normalized_call_id = call_id.strip()
    if not normalized_call_id:
        return
    drain_result = drain_pending_tool_output_deltas_locked(
        runtime=runtime,
        call_id=normalized_call_id,
    )
    if drain_result is None:
        return
    if drain_result.has_output:
        tool_payload = build_latest_tool_update_payload(
            runtime=runtime,
            call_id=normalized_call_id,
            result=drain_result.tool_result,
        )
        if tool_payload is None:
            raise StateError("Tool output update missing canonical tool payload state.")
        await flush_assistant_text_for_visible_events_locked(
            event_bus=event_bus,
            runtime=runtime,
            database_messages=database_messages,
        )
        await publish_tool_call_live_update_for_runtime(
            event_bus=event_bus,
            database_tool_calls=database_tool_calls,
            runtime=runtime,
            call_id=normalized_call_id,
            event_type="tool_call_updated",
            tool_payload=tool_payload,
            status=TOOL_CALL_STATUS_RUNNING,
            duration_ms=None,
            started_at_ms=runtime.tool_call_started_at_ms_by_call_id.get(normalized_call_id),
            tool_result=drain_result.tool_result,
        )
    if not drain_result.has_output:
        await flush_assistant_text_for_visible_events_locked(
            event_bus=event_bus,
            runtime=runtime,
            database_messages=database_messages,
        )


async def flush_pending_tool_events(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
) -> None:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        await flush_pending_tool_events_locked(
            event_bus=event_bus,
            runtime=runtime,
            database_messages=database_messages,
            database_tool_calls=database_tool_calls,
        )


async def flush_pending_tool_events_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
) -> None:
    await flush_assistant_text_for_visible_events_locked(
        event_bus=event_bus,
        runtime=runtime,
        database_messages=database_messages,
    )
    pending = runtime.pending_tool_events
    if not pending:
        return
    flushable: list[PendingToolEvent] = []
    remaining: list[PendingToolEvent] = []
    for item in pending:
        if item.thinking_index_before <= runtime.thinking_phase_cursor:
            flushable.append(item)
        else:
            remaining.append(item)
    if not flushable:
        runtime.pending_tool_events = remaining
        return
    event_type_order = {
        "tool_call_created": 0,
        "tool_call_started": 1,
        "tool_call_completed": 2,
    }
    flushable.sort(key=lambda row: (row.sequence_index, event_type_order.get(row.event_type, 99)))
    for index, item in enumerate(flushable):
        published_visible_event = False
        try:
            visible_content_boundary = await flush_assistant_text_for_visible_events_locked(
                event_bus=event_bus,
                runtime=runtime,
                database_messages=database_messages,
            )
            normalize_tool_payload_content_anchor_locked(
                runtime=runtime,
                tool_payload=item.tool_payload,
                content_boundary=visible_content_boundary,
            )
            cache_tool_call_layout_from_payload(runtime, item.tool_payload)
            record_latest_tool_payload_locked(runtime, item.tool_payload)
            call_id_value = item.tool_payload.get("call_id")
            normalized_call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
            if item.event_type == "tool_call_created":
                await persist_tool_call_created_projection(
                    runtime=runtime,
                    database_tool_calls=database_tool_calls,
                    tool_payload=item.tool_payload,
                )
            if item.event_type == "tool_call_completed" and normalized_call_id:
                await flush_pending_tool_output_deltas_for_call_id_locked(
                    event_bus=event_bus,
                    runtime=runtime,
                    database_messages=database_messages,
                    database_tool_calls=database_tool_calls,
                    call_id=normalized_call_id,
                )
                visible_content_boundary = await flush_assistant_text_for_visible_events_locked(
                    event_bus=event_bus,
                    runtime=runtime,
                    database_messages=database_messages,
                )
                normalize_tool_payload_content_anchor_locked(
                    runtime=runtime,
                    tool_payload=item.tool_payload,
                    content_boundary=visible_content_boundary,
                )
                cache_tool_call_layout_from_payload(runtime, item.tool_payload)
                record_latest_tool_payload_locked(runtime, item.tool_payload)
                await publish_completed_tool_live_update_locked(
                    event_bus=event_bus,
                    runtime=runtime,
                    database_tool_calls=database_tool_calls,
                    call_id=normalized_call_id,
                    tool_payload=item.tool_payload,
                )
            await complete_processing_activity_and_publish_visible_event_locked(
                event_bus=event_bus,
                runtime=runtime,
                database_messages=database_messages,
                event_type=item.event_type,
                payload={
                    "assistant_at_ms": runtime.assistant_at_ms,
                    "tool": build_tool_event_payload_preview(item.tool_payload),
                },
            )
            published_visible_event = True
            if normalized_call_id:
                runtime.emitted_tool_call_ids.add(normalized_call_id)
                if item.event_type == "tool_call_started":
                    record_tool_call_started_locked(
                        runtime=runtime,
                        call_id=normalized_call_id,
                    )
                    runtime.emitted_tool_call_started_ids.add(normalized_call_id)
                    started_at_ms = item.tool_payload.get("started_at_ms")
                    if (
                        isinstance(started_at_ms, int)
                        and not isinstance(started_at_ms, bool)
                        and started_at_ms >= 0
                    ):
                        runtime.tool_call_started_at_ms_by_call_id[normalized_call_id] = (
                            started_at_ms
                        )
                if item.event_type == "tool_call_completed":
                    record_tool_call_completed_locked(
                        runtime=runtime,
                        call_id=normalized_call_id,
                    )
                    runtime.tool_call_started_at_ms_by_call_id.pop(normalized_call_id, None)
                    runtime.post_terminal_tool_call_ids.discard(normalized_call_id)
        except RECOVERABLE_EXCEPTIONS:
            restart_index = index + 1 if published_visible_event else index
            runtime.pending_tool_events = flushable[restart_index:] + remaining
            raise
    runtime.pending_tool_events = remaining
