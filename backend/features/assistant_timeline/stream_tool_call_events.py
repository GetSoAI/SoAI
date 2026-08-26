"""SoAI - Shared assistant timeline tool call pending-event helpers [backend/features/assistant_timeline/stream_tool_call_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from core.validation.strings import coerce_required_non_empty_str
from features.assistant_timeline.models import (
    AssistantTimelineRuntime,
    PendingToolEvent,
)
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.tool_events_state import (
    find_pending_tool_event_locked,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("queue_synthetic_tool_call_created_if_missing",)


def resolve_tool_name(call: JSONDict) -> str:
    function_value = call.get("function")
    function_name = function_value.get("name") if isinstance(function_value, dict) else None
    return coerce_required_non_empty_str(
        function_name,
        label="Streamed tool call function name",
    )


def queue_synthetic_tool_call_created_if_missing_locked(
    *,
    runtime: AssistantTimelineRuntime,
    call: JSONDict,
    call_id: str,
    content_index_before: int,
    thinking_index_before: int,
    explicit_sequence_index: int,
) -> None:
    if call_id in runtime.emitted_tool_call_ids:
        return
    if (
        find_pending_tool_event_locked(
            runtime=runtime,
            event_type="tool_call_created",
            call_id=call_id,
        )
        is not None
    ):
        return
    if isinstance(explicit_sequence_index, bool) or explicit_sequence_index < 0:
        raise ValidationError(
            "Streamed tool call explicit sequence_index must be a non-negative integer.",
        )
    sequence_index = int(explicit_sequence_index)
    tool_payload: JSONDict = {
        "call_id": call_id,
        "tool_name": resolve_tool_name(call),
        "status": "pending",
        "message_index": runtime.message_index,
        "assistant_turn_at_ms": runtime.assistant_turn_at_ms,
        "model_variant_index": runtime.model_variant_index,
        "sequence_index": sequence_index,
        "content_index_before": content_index_before,
        "thinking_index_before": thinking_index_before,
        "collapsed": True,
    }
    if runtime.agent_turn_id is not None and runtime.agent_turn_id.strip():
        tool_payload["turn_id"] = runtime.agent_turn_id.strip()
    thinking_duration_before_value = coerce_optional_non_negative_int_strict(
        call.get("thinking_duration_before_ms"),
    )
    if thinking_duration_before_value is not None:
        tool_payload["thinking_duration_before_ms"] = thinking_duration_before_value
    pending_events = runtime.pending_tool_events
    if pending_events is None:
        pending_events = []
        runtime.pending_tool_events = pending_events
    pending_events.append(
        PendingToolEvent(
            sequence_index=sequence_index,
            thinking_index_before=thinking_index_before,
            event_type="tool_call_created",
            tool_payload=tool_payload,
        ),
    )


async def queue_synthetic_tool_call_created_if_missing(
    *,
    runtime: AssistantTimelineRuntime,
    call: JSONDict,
    call_id: str,
    content_index_before: int,
    thinking_index_before: int,
    explicit_sequence_index: int,
) -> None:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        queue_synthetic_tool_call_created_if_missing_locked(
            runtime=runtime,
            call=call,
            call_id=call_id,
            content_index_before=content_index_before,
            thinking_index_before=thinking_index_before,
            explicit_sequence_index=explicit_sequence_index,
        )
