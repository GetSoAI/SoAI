"""SoAI - Visible activity completion and event emission [backend/features/assistant_timeline/visible_activity_event_emission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_calls.chronology import (
    bound_required_chronology_anchor,
    resolve_required_non_negative_integer,
)
from core.types.json import is_json_dict
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from core.validation.strings import coerce_required_non_empty_str
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_STATUS_COMPLETED,
)
from features.assistant_timeline.assistant_text import (
    flush_assistant_visible_chronology_locked,
)
from features.assistant_timeline.processing_activity import (
    complete_processing_activity_if_running_locked,
)
from features.assistant_timeline.tool_event_layout import resolve_tool_call_layout
from features.assistant_timeline.visible_activity_publishing import (
    publish_chat_stream_event_after_visible_activity_locked,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "complete_processing_activity_and_publish_visible_event_locked",
    "flush_assistant_text_for_visible_events_locked",
    "flush_assistant_text_then_publish_visible_event_locked",
    "normalize_tool_payload_content_anchor_locked",
    "normalize_visible_event_payload_after_text_flush_locked",
)

TOOL_VISIBLE_EVENT_TYPES: frozenset[str] = frozenset(
    ("tool_call_created", "tool_call_started", "tool_call_completed"),
)


def normalize_tool_payload_content_anchor_locked(
    *,
    runtime: AssistantTimelineRuntime,
    tool_payload: JSONDict,
    content_boundary: int,
) -> None:
    content_index_before = resolve_required_non_negative_integer(
        tool_payload.get("content_index_before"),
        "content_index_before",
        field_label="Assistant timeline tool payload",
    )
    call_id = coerce_required_non_empty_str(
        tool_payload.get("call_id"),
        label="Assistant timeline tool payload 'call_id'",
    )
    layout = resolve_tool_call_layout(runtime, call_id)
    stable_boundary = layout.content_index_before if layout is not None else None
    if stable_boundary is None:
        stable_boundary = content_boundary
    elif stable_boundary > content_boundary:
        raise ValidationError("Assistant timeline tool layout exceeds visible content boundary.")
    if content_index_before == stable_boundary:
        return
    tool_payload["content_index_before"] = stable_boundary


def normalize_visible_event_payload_after_text_flush_locked(
    *,
    runtime: AssistantTimelineRuntime,
    event_type: str,
    payload: JSONDict,
    content_boundary: int,
) -> None:
    if event_type in TOOL_VISIBLE_EVENT_TYPES:
        tool_payload = payload.get("tool")
        if not is_json_dict(tool_payload):
            return
        normalize_tool_payload_content_anchor_locked(
            runtime=runtime,
            tool_payload=tool_payload,
            content_boundary=content_boundary,
        )
        return
    if event_type != "thinking_phase":
        return
    thinking_payload = payload.get("thinking_phase")
    if not is_json_dict(thinking_payload):
        return
    anchor_type_value = thinking_payload.get("anchor_type")
    anchor_position = coerce_optional_non_negative_int_strict(
        thinking_payload.get("anchor_position"),
    )
    if anchor_type_value == "position":
        thinking_payload["anchor_position"] = bound_required_chronology_anchor(
            anchor_position if anchor_position is not None else 0,
            "anchor_position",
            upper_bound=content_boundary,
            field_label="Assistant timeline thinking phase payload",
        )


async def complete_processing_activity_and_publish_visible_event_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_type: str,
    payload: JSONDict,
) -> None:
    await complete_processing_activity_if_running_locked(
        runtime=runtime,
        event_bus=event_bus,
        database_messages=database_messages,
        status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
    )
    await publish_chat_stream_event_after_visible_activity_locked(
        event_bus=event_bus,
        runtime=runtime,
        database_messages=database_messages,
        event_type=event_type,
        payload=payload,
    )


async def flush_assistant_text_for_visible_events_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
) -> int:
    return await flush_assistant_visible_chronology_locked(
        runtime=runtime,
        database_messages=database_messages,
        event_bus=event_bus,
    )


async def flush_assistant_text_then_publish_visible_event_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_type: str,
    payload: JSONDict,
) -> None:
    content_boundary = await flush_assistant_text_for_visible_events_locked(
        event_bus=event_bus,
        runtime=runtime,
        database_messages=database_messages,
    )
    normalize_visible_event_payload_after_text_flush_locked(
        runtime=runtime,
        event_type=event_type,
        payload=payload,
        content_boundary=content_boundary,
    )
    await complete_processing_activity_and_publish_visible_event_locked(
        event_bus=event_bus,
        runtime=runtime,
        database_messages=database_messages,
        event_type=event_type,
        payload=payload,
    )
