"""SoAI - Shared assistant timeline tool event handling [backend/features/assistant_timeline/tool_events_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.types_system import ToolCallOutputDeltaEvent
from core.timing.monotonic import monotonic_ms
from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from core.tool_calls.tool_event_payloads import build_normalized_tool_payload
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.pending_tool_event_sequence_rebasing import (
    rebase_pending_tool_event_sequences_for_reservation_locked,
)
from features.assistant_timeline.post_terminal_tool_events import (
    handle_post_terminal_tool_event_locked,
    runtime_requires_post_terminal_tool_projection,
)
from features.assistant_timeline.status_preview_state import (
    clear_status_preview_state,
    record_status_preview_tool_completion,
)
from features.assistant_timeline.tool_event_canonicalization import (
    patch_pending_tool_call_created_payload_locked,
    rewrite_tool_event_to_canonical_layout_if_available,
    validate_tool_event_matches_canonical_layout_if_available,
)
from features.assistant_timeline.tool_event_layout import is_known_tool_call
from features.assistant_timeline.tool_event_normalization import (
    event_matches_runtime,
    normalize_tool_call_event,
)
from features.assistant_timeline.tool_event_projection_layout import (
    rewrite_tool_event_to_persisted_projection_layout_locked,
)
from features.assistant_timeline.tool_events_flushing import (
    flush_pending_tool_events_locked,
)
from features.assistant_timeline.tool_events_state import (
    find_pending_tool_event_locked,
    queue_pending_tool_event_locked,
)
from features.assistant_timeline.tool_output_deltas import (
    handle_tool_output_delta_event_locked,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.events.types_base import Event
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = (
    "ToolEventsHandlingResult",
    "allow_post_terminal_tool_event",
    "handle_tool_event_locked",
)


@dataclass(frozen=True, slots=True)
class ToolEventsHandlingResult:
    should_wake_status_preview: bool = False
    should_unsubscribe: bool = False


def allow_post_terminal_tool_event(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
    tool_name: str,
) -> bool:
    if not runtime_requires_post_terminal_tool_projection(runtime):
        return True
    if tool_name == "subagent_spawn" and call_id:
        runtime.post_terminal_tool_call_ids.add(call_id)
    return bool(call_id) and (
        call_id in runtime.post_terminal_tool_call_ids or is_known_tool_call(runtime, call_id)
    )


async def handle_tool_event_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    event: Event,
) -> ToolEventsHandlingResult:
    if isinstance(event, ToolCallOutputDeltaEvent):
        await handle_tool_output_delta_event_locked(
            event_bus=event_bus,
            runtime=runtime,
            database_messages=database_messages,
            database_tool_calls=database_tool_calls,
            event=event,
        )
        return ToolEventsHandlingResult()
    normalized_event = normalize_tool_call_event(event, runtime)
    if normalized_event is None:
        return ToolEventsHandlingResult()
    if not event_matches_runtime(event, runtime, normalized_event):
        return ToolEventsHandlingResult()
    normalized_event = await rewrite_tool_event_to_persisted_projection_layout_locked(
        runtime=runtime,
        database_tool_calls=database_tool_calls,
        normalized_event=normalized_event,
    )
    if normalized_event.event_type in ("tool_call_started", "tool_call_completed"):
        validate_tool_event_matches_canonical_layout_if_available(runtime, normalized_event)
        normalized_event = rewrite_tool_event_to_canonical_layout_if_available(
            runtime,
            normalized_event,
        )
    normalized_call_id = normalized_event.call_id
    if (
        normalized_event.event_type == "tool_call_created"
        and normalized_call_id
        and normalized_event.tool_name == "subagent_spawn"
    ):
        runtime.post_terminal_tool_call_ids.add(normalized_call_id)
    if normalized_event.event_type == "tool_call_created" and normalized_call_id:
        if normalized_call_id in runtime.emitted_tool_call_ids:
            return ToolEventsHandlingResult()
        pending_created = find_pending_tool_event_locked(
            runtime=runtime,
            event_type="tool_call_created",
            call_id=normalized_call_id,
        )
        if pending_created is not None:
            authoritative_payload = build_normalized_tool_payload(normalized_event)
            patch_pending_tool_call_created_payload_locked(
                pending_item=pending_created,
                authoritative_payload=authoritative_payload,
            )
            return ToolEventsHandlingResult()
    if (
        normalized_event.event_type == "tool_call_started"
        and normalized_call_id
        and (
            normalized_call_id in runtime.started_tool_call_ids
            or normalized_call_id in runtime.completed_tool_call_ids
            or find_pending_tool_event_locked(
                runtime=runtime,
                event_type="tool_call_started",
                call_id=normalized_call_id,
            )
            is not None
        )
    ):
        return ToolEventsHandlingResult()
    if (
        normalized_event.event_type == "tool_call_completed"
        and normalized_call_id
        and (
            normalized_call_id in runtime.completed_tool_call_ids
            or find_pending_tool_event_locked(
                runtime=runtime,
                event_type="tool_call_completed",
                call_id=normalized_call_id,
            )
            is not None
        )
    ):
        return ToolEventsHandlingResult()
    if (
        normalized_event.event_type == "tool_call_created"
        and normalized_event.tool_name == CONTEXT_COMPACTION_TOOL_NAME
    ):
        rebase_pending_tool_event_sequences_for_reservation_locked(
            runtime=runtime,
            reserved_sequence_index=normalized_event.sequence_index,
        )
    tool_payload = build_normalized_tool_payload(normalized_event)
    handled_post_terminal_event = await handle_post_terminal_tool_event_locked(
        event_bus=event_bus,
        runtime=runtime,
        database_tool_calls=database_tool_calls,
        normalized_event=normalized_event,
        tool_payload=tool_payload,
    )
    if handled_post_terminal_event:
        should_unsubscribe = (
            normalized_event.event_type == "tool_call_completed"
            and runtime.detach_event is not None
            and runtime.detach_event.is_set()
            and (runtime.terminal_event_emitted or runtime.terminal_finalization_started)
            and not runtime.post_terminal_tool_call_ids
        )
        return ToolEventsHandlingResult(should_unsubscribe=should_unsubscribe)
    if normalized_event.event_type == "tool_call_created":
        clear_status_preview_state(
            runtime=runtime,
            now_ms=monotonic_ms(),
        )
    queue_pending_tool_event_locked(
        runtime=runtime,
        event_type=normalized_event.event_type,
        tool_payload=tool_payload,
        sequence_index=normalized_event.sequence_index,
        thinking_index_before=normalized_event.thinking_index_before,
    )
    await flush_pending_tool_events_locked(
        event_bus=event_bus,
        runtime=runtime,
        database_messages=database_messages,
        database_tool_calls=database_tool_calls,
    )
    should_wake_status_preview = False
    if normalized_event.event_type == "tool_call_completed":
        should_wake_status_preview = record_status_preview_tool_completion(
            runtime=runtime,
            tool_payload=tool_payload,
        )
    should_unsubscribe = (
        normalized_event.event_type == "tool_call_completed"
        and runtime.detach_event is not None
        and runtime.detach_event.is_set()
        and (runtime.terminal_event_emitted or runtime.terminal_finalization_started)
        and not runtime.post_terminal_tool_call_ids
    )
    return ToolEventsHandlingResult(
        should_wake_status_preview=should_wake_status_preview,
        should_unsubscribe=should_unsubscribe,
    )
