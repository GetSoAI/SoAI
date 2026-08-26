"""SoAI - Tool-call event payload normalization [backend/core/tool_calls/tool_event_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.events.types_conversation import (
    ToolCallCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallStartedEvent,
)
from core.tool_calls.tool_payloads import build_tool_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

    type ToolCallSystemEvent = ToolCallCreatedEvent | ToolCallStartedEvent | ToolCallCompletedEvent

__all__ = (
    "NormalizedToolCallEvent",
    "build_normalized_tool_payload",
    "map_tool_call_event_to_tool_payload",
    "normalize_system_tool_call_event",
    "replace_normalized_tool_call_event_layout",
)


@dataclass(frozen=True, slots=True)
class NormalizedToolCallEvent:
    event_type: str
    status: str
    call_id: str
    tool_name: str
    message_index: int
    turn_id: str | None
    iteration_index: int | None
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None = None
    started_at_ms: int | None = None
    arguments: str | None = None
    result: JSONValue | None = None
    error: str | None = None
    duration_ms: int | None = None
    code_diffs: list[JSONDict] | None = None


def replace_normalized_tool_call_event_layout(
    normalized: NormalizedToolCallEvent,
    *,
    tool_name: str,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
    thinking_duration_before_ms: int | None,
) -> NormalizedToolCallEvent:
    return replace(
        normalized,
        tool_name=tool_name,
        sequence_index=sequence_index,
        content_index_before=content_index_before,
        thinking_index_before=thinking_index_before,
        thinking_duration_before_ms=thinking_duration_before_ms,
    )


def normalize_system_tool_call_event(event: ToolCallSystemEvent) -> NormalizedToolCallEvent:
    status = "pending"
    event_type = "tool_call_created"
    result = None
    error: str | None = None
    duration_ms: int | None = None
    code_diffs: list[JSONDict] | None = None
    if isinstance(event, ToolCallStartedEvent):
        status = "running"
        event_type = "tool_call_started"
    elif isinstance(event, ToolCallCompletedEvent):
        status = event.status
        event_type = "tool_call_completed"
        result = event.result
        error = event.error_message
        duration_ms = event.duration_ms
        code_diffs = event.code_diffs
    return NormalizedToolCallEvent(
        event_type=event_type,
        status=status,
        call_id=event.call_id,
        tool_name=event.tool_name,
        message_index=event.message_index,
        turn_id=event.turn_id,
        iteration_index=event.iteration_index,
        sequence_index=event.sequence_index,
        content_index_before=event.content_index_before,
        thinking_index_before=event.thinking_index_before,
        thinking_duration_before_ms=event.thinking_duration_before_ms,
        started_at_ms=event.started_at_ms if isinstance(event, ToolCallStartedEvent) else None,
        arguments=event.tool_arguments,
        result=result,
        error=error,
        duration_ms=duration_ms,
        code_diffs=code_diffs,
    )


def build_normalized_tool_payload(normalized: NormalizedToolCallEvent) -> JSONDict:
    return build_tool_payload(
        call_id=normalized.call_id,
        tool_name=normalized.tool_name,
        status=normalized.status,
        message_index=normalized.message_index,
        sequence_index=normalized.sequence_index,
        content_index_before=normalized.content_index_before,
        thinking_index_before=normalized.thinking_index_before,
        collapsed=True,
        turn_id=normalized.turn_id,
        iteration_index=normalized.iteration_index,
        arguments=normalized.arguments,
        started_at_ms=normalized.started_at_ms,
        result=normalized.result,
        error=normalized.error,
        duration_ms=normalized.duration_ms,
        thinking_duration_before_ms=normalized.thinking_duration_before_ms,
        code_diffs=normalized.code_diffs,
    )


def map_tool_call_event_to_tool_payload(event: ToolCallSystemEvent) -> JSONDict:
    return build_normalized_tool_payload(normalize_system_tool_call_event(event))
