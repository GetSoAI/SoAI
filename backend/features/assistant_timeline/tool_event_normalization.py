"""SoAI - Assistant timeline tool-call event matching [backend/features/assistant_timeline/tool_event_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_conversation import (
    ToolCallCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallStartedEvent,
)
from core.tool_calls.tool_event_payloads import (
    NormalizedToolCallEvent,
    normalize_system_tool_call_event,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.runtime_matching import (
    matches_assistant_timeline_runtime,
)

if TYPE_CHECKING:
    from core.events.types_base import Event

__all__ = (
    "NormalizedToolCallEvent",
    "event_matches_runtime",
    "normalize_tool_call_event",
)


def normalize_tool_call_event(
    event: Event,
    runtime: AssistantTimelineRuntime,
) -> NormalizedToolCallEvent | None:
    _ = runtime
    if not isinstance(event, ToolCallCreatedEvent | ToolCallStartedEvent | ToolCallCompletedEvent):
        return None
    return normalize_system_tool_call_event(event)


def event_matches_runtime(
    event: Event,
    runtime: AssistantTimelineRuntime,
    normalized: NormalizedToolCallEvent,
) -> bool:
    if not isinstance(event, ToolCallCreatedEvent | ToolCallStartedEvent | ToolCallCompletedEvent):
        return False
    return matches_assistant_timeline_runtime(
        runtime=runtime,
        event_user_id=event.user_id,
        event_conv_id=event.conv_id,
        event_message_index=normalized.message_index,
        event_turn_id=normalized.turn_id,
    )
