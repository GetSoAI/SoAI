"""SoAI - Assistant timeline persisted tool projection layout resolution [backend/features/assistant_timeline/tool_event_projection_layout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_calls.chronology import resolve_tool_call_chronology_fields
from core.tool_calls.tool_event_payloads import (
    NormalizedToolCallEvent,
    replace_normalized_tool_call_event_layout,
)
from features.assistant_timeline.tool_event_canonicalization import (
    rewrite_tool_event_to_canonical_layout_if_available,
)
from features.assistant_timeline.tool_event_layout import (
    cache_tool_call_layout_from_payload,
)

if TYPE_CHECKING:
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("rewrite_tool_event_to_persisted_projection_layout_locked",)


def _trimmed_string(value: JSONValue | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def _validate_cached_identity(
    runtime: AssistantTimelineRuntime,
    normalized_event: NormalizedToolCallEvent,
) -> None:
    identity = runtime.tool_call_identity_by_call_id.get(normalized_event.call_id.strip())
    if identity is None:
        return
    if (
        normalized_event.message_index != identity.message_index
        or (normalized_event.turn_id is not None and normalized_event.turn_id != identity.turn_id)
        or (
            normalized_event.iteration_index is not None
            and normalized_event.iteration_index != identity.iteration_index
        )
    ):
        raise ValidationError("Assistant timeline tool identity changed for existing call ID.")
    layout = runtime.tool_call_layout_by_call_id.get(normalized_event.call_id.strip())
    if (
        layout is not None
        and normalized_event.turn_id is not None
        and (
            normalized_event.sequence_index != layout.sequence_index
            or normalized_event.content_index_before != layout.content_index_before
            or normalized_event.thinking_index_before != layout.thinking_index_before
        )
    ):
        raise ValidationError(
            "Assistant timeline authoritative tool chronology conflicts with pending layout."
        )


def _rewrite_from_projection(
    normalized_event: NormalizedToolCallEvent,
    projection: JSONDict,
) -> NormalizedToolCallEvent:
    chronology = resolve_tool_call_chronology_fields(
        projection,
        field_label="Persisted tool projection",
    )
    if normalized_event.turn_id is not None and normalized_event.iteration_index is not None:
        if (
            normalized_event.sequence_index != chronology.sequence_index
            or normalized_event.content_index_before != chronology.content_index_before
            or normalized_event.thinking_index_before != chronology.thinking_index_before
        ):
            raise ValidationError(
                "Assistant timeline authoritative tool chronology conflicts with persisted layout."
            )
    projection_tool_name = _trimmed_string(projection.get("tool_name"))
    return replace_normalized_tool_call_event_layout(
        normalized_event,
        tool_name=projection_tool_name or normalized_event.tool_name,
        sequence_index=chronology.sequence_index,
        content_index_before=chronology.content_index_before,
        thinking_index_before=chronology.thinking_index_before,
        thinking_duration_before_ms=chronology.thinking_duration_before_ms,
    )


async def rewrite_tool_event_to_persisted_projection_layout_locked(
    *,
    runtime: AssistantTimelineRuntime,
    database_tool_calls: DatabaseToolCallsProtocol,
    normalized_event: NormalizedToolCallEvent,
) -> NormalizedToolCallEvent:
    call_id = normalized_event.call_id.strip()
    if not call_id:
        return normalized_event
    _validate_cached_identity(runtime, normalized_event)
    if call_id in runtime.tool_call_layout_by_call_id:
        return rewrite_tool_event_to_canonical_layout_if_available(runtime, normalized_event)
    projection = await database_tool_calls.get_tool_call_by_identity(
        conv_id=runtime.conv_id,
        call_id=call_id,
        turn_id=normalized_event.turn_id,
        iteration_index=normalized_event.iteration_index,
        message_index=normalized_event.message_index,
        assistant_turn_at_ms=runtime.assistant_turn_at_ms,
        model_variant_index=runtime.model_variant_index,
    )
    if projection is None:
        return normalized_event
    rewritten = _rewrite_from_projection(normalized_event, projection)
    cache_tool_call_layout_from_payload(runtime, projection)
    return rewritten
