"""SoAI - Tool call event guard helpers [backend/core/events/tool_call_event_guards.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, TypeGuard

from core.events.types_base import Event
from core.events.types_system import (
    ToolCallCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallOutputDeltaEvent,
    ToolCallStartedEvent,
)

__all__ = ("is_tool_call_stream_event",)

if TYPE_CHECKING:
    type ToolCallStreamEvent = (
        ToolCallCreatedEvent
        | ToolCallStartedEvent
        | ToolCallCompletedEvent
        | ToolCallOutputDeltaEvent
    )


def is_tool_call_stream_event(event: Event) -> TypeGuard[ToolCallStreamEvent]:
    return isinstance(
        event,
        ToolCallCreatedEvent
        | ToolCallStartedEvent
        | ToolCallCompletedEvent
        | ToolCallOutputDeltaEvent,
    )
