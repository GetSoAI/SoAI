"""SoAI - Shared assistant timeline tool event canonicalization helpers [backend/features/assistant_timeline/tool_event_canonicalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_calls.tool_event_payloads import (
    NormalizedToolCallEvent,
    replace_normalized_tool_call_event_layout,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.assistant_timeline.models import (
        AssistantTimelineRuntime,
        PendingToolEvent,
    )

__all__ = (
    "patch_pending_tool_call_created_payload_locked",
    "rewrite_tool_event_to_canonical_layout_if_available",
    "validate_tool_event_matches_canonical_layout_if_available",
)


def patch_pending_tool_call_created_payload_locked(
    *,
    pending_item: PendingToolEvent,
    authoritative_payload: JSONDict,
) -> None:
    pending_item.tool_payload.clear()
    pending_item.tool_payload.update(authoritative_payload)
    sequence_index_value = pending_item.tool_payload.get("sequence_index")
    if isinstance(sequence_index_value, int):
        pending_item.sequence_index = sequence_index_value
    thinking_index_before_value = pending_item.tool_payload.get("thinking_index_before")
    if isinstance(thinking_index_before_value, int):
        pending_item.thinking_index_before = thinking_index_before_value


def rewrite_tool_event_to_canonical_layout_if_available(
    runtime: AssistantTimelineRuntime,
    normalized_event: NormalizedToolCallEvent,
) -> NormalizedToolCallEvent:
    call_id = normalized_event.call_id.strip()
    if not call_id:
        return normalized_event
    layout = runtime.tool_call_layout_by_call_id.get(call_id)
    canonical_tool_name = runtime.tool_name_by_call_id.get(call_id)
    if layout is None and not canonical_tool_name:
        return normalized_event
    resolved_tool_name = canonical_tool_name or normalized_event.tool_name
    if layout is None:
        if normalized_event.tool_name == resolved_tool_name:
            return normalized_event
        return replace_normalized_tool_call_event_layout(
            normalized_event,
            tool_name=resolved_tool_name,
            sequence_index=normalized_event.sequence_index,
            content_index_before=normalized_event.content_index_before,
            thinking_index_before=normalized_event.thinking_index_before,
            thinking_duration_before_ms=normalized_event.thinking_duration_before_ms,
        )
    resolved_thinking_duration_before_ms = normalized_event.thinking_duration_before_ms
    if layout.thinking_duration_before_ms is not None:
        resolved_thinking_duration_before_ms = layout.thinking_duration_before_ms
    if (
        normalized_event.sequence_index == layout.sequence_index
        and normalized_event.content_index_before == layout.content_index_before
        and normalized_event.thinking_index_before == layout.thinking_index_before
        and normalized_event.tool_name == resolved_tool_name
        and resolved_thinking_duration_before_ms == normalized_event.thinking_duration_before_ms
    ):
        return normalized_event
    return replace_normalized_tool_call_event_layout(
        normalized_event,
        tool_name=resolved_tool_name,
        sequence_index=layout.sequence_index,
        content_index_before=layout.content_index_before,
        thinking_index_before=layout.thinking_index_before,
        thinking_duration_before_ms=resolved_thinking_duration_before_ms,
    )


def validate_tool_event_matches_canonical_layout_if_available(
    runtime: AssistantTimelineRuntime,
    normalized_event: NormalizedToolCallEvent,
) -> None:
    call_id = normalized_event.call_id.strip()
    if not call_id:
        return
    layout = runtime.tool_call_layout_by_call_id.get(call_id)
    if layout is None:
        return
    if (
        normalized_event.sequence_index == layout.sequence_index
        and normalized_event.content_index_before == layout.content_index_before
        and normalized_event.thinking_index_before == layout.thinking_index_before
    ):
        return
    raise ValidationError(
        "Assistant timeline authoritative tool chronology conflicts with pending layout.",
    )
