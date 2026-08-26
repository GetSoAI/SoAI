"""SoAI - Shared assistant timeline tool event state tracking [backend/features/assistant_timeline/tool_events_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.assistant_timeline.models import (
    AssistantTimelineRuntime,
    PendingToolEvent,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "discard_pending_tool_events_for_call_id_locked",
    "find_pending_tool_event_locked",
    "queue_pending_tool_event_locked",
    "record_tool_call_completed_locked",
    "record_tool_call_started_locked",
)


def find_pending_tool_event_locked(
    *,
    runtime: AssistantTimelineRuntime,
    event_type: str,
    call_id: str,
) -> PendingToolEvent | None:
    normalized_call_id = call_id.strip()
    if not normalized_call_id:
        return None
    pending_events = runtime.pending_tool_events
    if not pending_events:
        return None
    for pending_event in pending_events:
        if pending_event.event_type != event_type:
            continue
        pending_call_id_value = pending_event.tool_payload.get("call_id")
        if (
            isinstance(pending_call_id_value, str)
            and pending_call_id_value.strip() == normalized_call_id
        ):
            return pending_event
    return None


def record_tool_call_started_locked(*, runtime: AssistantTimelineRuntime, call_id: str) -> bool:
    normalized_call_id = call_id.strip()
    if not normalized_call_id:
        return False
    if normalized_call_id in runtime.completed_tool_call_ids:
        return False
    if normalized_call_id in runtime.started_tool_call_ids:
        return False
    runtime.started_tool_call_ids.add(normalized_call_id)
    runtime.running_tool_call_ids.add(normalized_call_id)
    return True


def record_tool_call_completed_locked(*, runtime: AssistantTimelineRuntime, call_id: str) -> bool:
    normalized_call_id = call_id.strip()
    if not normalized_call_id:
        return False
    if normalized_call_id in runtime.completed_tool_call_ids:
        return False
    runtime.completed_tool_call_ids.add(normalized_call_id)
    runtime.running_tool_call_ids.discard(normalized_call_id)
    return True


def discard_pending_tool_events_for_call_id_locked(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
) -> None:
    normalized_call_id = call_id.strip()
    if not normalized_call_id:
        return
    pending_events = runtime.pending_tool_events
    if not pending_events:
        return
    remaining_events: list[PendingToolEvent] = []
    for pending_event in pending_events:
        pending_call_id_value = pending_event.tool_payload.get("call_id")
        pending_call_id = (
            pending_call_id_value.strip() if isinstance(pending_call_id_value, str) else ""
        )
        if pending_call_id != normalized_call_id:
            remaining_events.append(pending_event)
    runtime.pending_tool_events = remaining_events


def queue_pending_tool_event_locked(
    *,
    runtime: AssistantTimelineRuntime,
    event_type: str,
    tool_payload: JSONDict,
    sequence_index: int,
    thinking_index_before: int,
) -> None:
    pending_tool_events = runtime.pending_tool_events
    if pending_tool_events is None:
        pending_tool_events = []
        runtime.pending_tool_events = pending_tool_events
    pending_tool_events.append(
        PendingToolEvent(
            sequence_index=sequence_index,
            thinking_index_before=thinking_index_before,
            event_type=event_type,
            tool_payload=tool_payload,
        ),
    )
