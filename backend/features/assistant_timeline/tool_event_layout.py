"""SoAI - Shared assistant timeline tool-call layout helpers [backend/features/assistant_timeline/tool_event_layout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.assistant_timeline.tool_sequence_ownership import (
    register_tool_call_sequence_index_owner,
)
from core.conversations.assistant_turn_variant_identity import (
    AssistantTurnVariantIdentity,
)
from core.errors.exceptions import ValidationError
from core.tool_calls.chronology import bound_required_chronology_anchor
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.assistant_timeline.models import (
    AssistantTimelineRuntime,
    ToolCallLayout,
    ToolCallPersistenceIdentity,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "cache_pending_tool_call_layout_from_runtime_locked",
    "cache_tool_call_layout",
    "cache_tool_call_layout_from_payload",
    "extract_layout_from_payload",
    "is_known_tool_call",
    "resolve_tool_call_identity",
    "resolve_tool_call_layout",
)


def extract_layout_from_payload(payload: JSONDict) -> ToolCallLayout | None:
    sequence_value = coerce_optional_non_negative_int_strict(payload.get("sequence_index"))
    content_index_before_value = coerce_optional_non_negative_int_strict(
        payload.get("content_index_before"),
    )
    thinking_index_before_value = coerce_optional_non_negative_int_strict(
        payload.get("thinking_index_before"),
    )
    if (
        sequence_value is None
        or content_index_before_value is None
        or thinking_index_before_value is None
    ):
        return None
    thinking_duration_before_value = payload.get("thinking_duration_before_ms")
    thinking_duration_before_ms: int | None = None
    if thinking_duration_before_value is not None:
        thinking_duration_before_ms = coerce_optional_non_negative_int_strict(
            thinking_duration_before_value,
        )
        if thinking_duration_before_ms is None:
            return None
    return ToolCallLayout(
        sequence_index=sequence_value,
        content_index_before=content_index_before_value,
        thinking_index_before=thinking_index_before_value,
        thinking_duration_before_ms=thinking_duration_before_ms,
    )


def cache_tool_call_layout(
    runtime: AssistantTimelineRuntime,
    call_id: str,
    layout: ToolCallLayout,
) -> None:
    existing_layout = runtime.tool_call_layout_by_call_id.get(call_id)
    if existing_layout is not None and _tool_call_layout_conflicts(existing_layout, layout):
        raise ValidationError(
            f"Assistant timeline tool chronology changed for call_id '{call_id}'.",
        )
    register_tool_call_sequence_index_owner(
        sequence_owner_by_sequence_index=runtime.tool_call_call_id_by_sequence_index,
        call_owner_by_call_id=runtime.tool_call_sequence_index_by_call_id,
        sequence_index=layout.sequence_index,
        call_id=call_id,
        source="Assistant timeline",
    )
    runtime.tool_call_layout_by_call_id[call_id] = layout


def cache_tool_call_layout_from_payload(
    runtime: AssistantTimelineRuntime,
    payload: JSONDict,
) -> None:
    call_id_value = payload.get("call_id")
    call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
    if not call_id:
        return
    layout = extract_layout_from_payload(payload)
    existing_layout = runtime.tool_call_layout_by_call_id.get(call_id)
    if existing_layout is not None and layout is not None:
        if existing_layout.content_index_before > runtime.assistant_visible_chars:
            raise ValidationError(
                "Assistant timeline tool layout exceeds assistant visible text length.",
            )
        if (
            existing_layout.sequence_index != layout.sequence_index
            or existing_layout.thinking_index_before != layout.thinking_index_before
        ):
            raise ValidationError(
                f"Assistant timeline tool chronology changed for call_id '{call_id}'.",
            )
    tool_name_value = payload.get("tool_name")
    tool_name = tool_name_value.strip() if isinstance(tool_name_value, str) else ""
    if tool_name:
        runtime.tool_name_by_call_id[call_id] = tool_name
    existing_identity = runtime.tool_call_identity_by_call_id.get(call_id)
    message_index_value = payload.get("message_index")
    message_index = (
        message_index_value
        if isinstance(message_index_value, int) and message_index_value >= 0
        else (
            existing_identity.message_index
            if existing_identity is not None
            else runtime.message_index
        )
    )
    turn_id_value = payload.get("turn_id")
    turn_id = None
    if isinstance(turn_id_value, str) and turn_id_value.strip():
        turn_id = turn_id_value.strip()
    if turn_id is None and existing_identity is not None:
        turn_id = existing_identity.turn_id
    if turn_id is None:
        runtime_turn_id = (
            runtime.agent_turn_id.strip()
            if isinstance(runtime.agent_turn_id, str) and runtime.agent_turn_id.strip()
            else None
        )
        if runtime_turn_id is not None:
            turn_id = runtime_turn_id
    iteration_index_value = payload.get("iteration_index")
    iteration_index = (
        iteration_index_value
        if isinstance(iteration_index_value, int) and iteration_index_value >= 0
        else (existing_identity.iteration_index if existing_identity is not None else None)
    )
    payload_assistant_turn_at_ms = coerce_optional_non_negative_int_strict(
        payload.get("assistant_turn_at_ms"),
    )
    payload_model_variant_index = coerce_optional_non_negative_int_strict(
        payload.get("model_variant_index"),
    )
    assistant_turn_at_ms = runtime.assistant_turn_at_ms
    model_variant_index = runtime.model_variant_index
    if payload_assistant_turn_at_ms is not None and payload_model_variant_index is not None:
        assistant_turn_at_ms = payload_assistant_turn_at_ms
        model_variant_index = payload_model_variant_index
    elif existing_identity is not None:
        assistant_turn_at_ms = existing_identity.assistant_identity.assistant_turn_at_ms
        model_variant_index = existing_identity.assistant_identity.model_variant_index
    runtime.tool_call_identity_by_call_id[call_id] = ToolCallPersistenceIdentity(
        message_index=message_index,
        assistant_identity=AssistantTurnVariantIdentity(
            assistant_at_ms=int(runtime.assistant_at_ms),
            assistant_turn_at_ms=int(assistant_turn_at_ms),
            model_variant_index=int(model_variant_index),
        ),
        turn_id=turn_id,
        iteration_index=iteration_index,
    )
    if layout is None:
        return
    if existing_layout is not None:
        payload["sequence_index"] = existing_layout.sequence_index
        payload["content_index_before"] = existing_layout.content_index_before
        payload["thinking_index_before"] = existing_layout.thinking_index_before
        if existing_layout.thinking_duration_before_ms is not None:
            payload["thinking_duration_before_ms"] = existing_layout.thinking_duration_before_ms
        elif "thinking_duration_before_ms" in payload:
            payload.pop("thinking_duration_before_ms", None)
        layout = existing_layout
    else:
        content_index_before = bound_required_chronology_anchor(
            layout.content_index_before,
            "content_index_before",
            upper_bound=runtime.assistant_visible_chars,
        )
        if content_index_before != layout.content_index_before:
            payload["content_index_before"] = content_index_before
            layout = ToolCallLayout(
                sequence_index=layout.sequence_index,
                content_index_before=content_index_before,
                thinking_index_before=layout.thinking_index_before,
                thinking_duration_before_ms=layout.thinking_duration_before_ms,
            )
    cache_tool_call_layout(runtime, call_id, layout)


def _tool_call_layout_conflicts(existing: ToolCallLayout, incoming: ToolCallLayout) -> bool:
    return (
        existing.sequence_index != incoming.sequence_index
        or existing.content_index_before != incoming.content_index_before
        or existing.thinking_index_before != incoming.thinking_index_before
    )


def cache_pending_tool_call_layout_from_runtime_locked(
    runtime: AssistantTimelineRuntime,
    call_id: str,
    content_boundary: int,
) -> None:
    if (
        call_id in runtime.tool_call_layout_by_call_id
        and call_id in runtime.tool_call_identity_by_call_id
    ):
        return
    pending = runtime.pending_tool_events
    if pending is None:
        return
    for pending_event in pending:
        pending_call_id_value = pending_event.tool_payload.get("call_id")
        pending_call_id = (
            pending_call_id_value.strip() if isinstance(pending_call_id_value, str) else ""
        )
        if pending_call_id != call_id:
            continue
        if call_id not in runtime.tool_call_layout_by_call_id:
            pending_event.tool_payload["content_index_before"] = content_boundary
        cache_tool_call_layout_from_payload(runtime, pending_event.tool_payload)
        return


def resolve_tool_call_layout(
    runtime: AssistantTimelineRuntime,
    call_id: str,
) -> ToolCallLayout | None:
    return runtime.tool_call_layout_by_call_id.get(call_id)


def resolve_tool_call_identity(
    runtime: AssistantTimelineRuntime,
    call_id: str,
) -> ToolCallPersistenceIdentity | None:
    return runtime.tool_call_identity_by_call_id.get(call_id)


def is_known_tool_call(runtime: AssistantTimelineRuntime, call_id: str) -> bool:
    if call_id in runtime.tool_call_layout_by_call_id:
        return True
    if call_id in runtime.emitted_tool_call_ids:
        return True
    if call_id in runtime.running_tool_call_ids:
        return True
    pending = runtime.pending_tool_events
    if pending is None:
        return False
    for pending_event in pending:
        pending_call_id_value = pending_event.tool_payload.get("call_id")
        pending_call_id = (
            pending_call_id_value.strip() if isinstance(pending_call_id_value, str) else ""
        )
        if pending_call_id == call_id:
            return True
    return False
