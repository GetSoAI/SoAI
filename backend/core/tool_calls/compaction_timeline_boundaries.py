"""SoAI - Compaction timeline boundary projection [backend/core/tool_calls/compaction_timeline_boundaries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.assistant_timeline.tool_sequence_ownership import (
    register_tool_call_sequence_index_owner,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.tool_calls.context_compaction_markers import (
    build_context_compaction_marker_from_tool_payload,
)
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_non_negative_strict_int

__all__ = ("normalize_timeline_boundary_entries",)


def _resolve_completed_tool_payload(event: JSONValue) -> JSONDict | None:
    event_dict = coerce_json_dict(normalize_for_json(event))
    if event_dict is None or event_dict.get("event_type") != "tool_call_completed":
        return None
    payload = coerce_json_dict(event_dict.get("payload"))
    if payload is None:
        raise ValidationError(
            "assistant_event_timeline completed tool entry requires a payload object.",
        )
    tool_payload = coerce_json_dict(payload.get("tool"))
    if tool_payload is None:
        raise ValidationError(
            "assistant_event_timeline completed tool entry requires a tool payload object.",
        )
    return tool_payload


def _resolve_required_tool_field(tool_payload: JSONDict, field_name: str) -> str:
    value = tool_payload.get(field_name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValidationError(
        f"assistant_event_timeline completed tool entry requires a {field_name}.",
    )


def _resolve_tool_sequence_index(tool_payload: JSONDict) -> int:
    sequence_index_value = tool_payload.get("sequence_index")
    if not is_non_negative_strict_int(sequence_index_value):
        raise ValidationError(
            "assistant_event_timeline completed tool entry requires a non-negative sequence_index.",
        )
    return int(sequence_index_value)


def normalize_timeline_boundary_entries(message: JSONDict) -> list[JSONDict]:
    role_value = message.get("role")
    role = role_value.strip() if isinstance(role_value, str) else ""
    timeline_value = message.get("assistant_event_timeline")
    if role != "assistant" or not isinstance(timeline_value, list):
        return []
    entries: list[JSONDict] = []
    sequence_owner_by_sequence_index: dict[int, str] = {}
    call_owner_by_call_id: dict[str, int] = {}
    completed_call_ids: set[str] = set()
    for event in timeline_value:
        tool_payload = _resolve_completed_tool_payload(event)
        if tool_payload is None:
            continue
        tool_call_id = _resolve_required_tool_field(tool_payload, "call_id")
        tool_name = _resolve_required_tool_field(tool_payload, "tool_name")
        register_tool_call_sequence_index_owner(
            sequence_owner_by_sequence_index=sequence_owner_by_sequence_index,
            call_owner_by_call_id=call_owner_by_call_id,
            sequence_index=_resolve_tool_sequence_index(tool_payload),
            call_id=tool_call_id,
            source="assistant_event_timeline boundary",
        )
        if tool_call_id in completed_call_ids:
            raise ValidationError(
                f"assistant_event_timeline contains duplicate completed tool entries for call_id '{tool_call_id}'.",
            )
        completed_call_ids.add(tool_call_id)
        if build_context_compaction_marker_from_tool_payload(tool_payload) is not None:
            continue
        entries.extend(
            (
                {
                    "soai_boundary_type": "tool_call",
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                },
                {
                    "soai_boundary_type": "tool_result",
                    "tool_call_id": tool_call_id,
                },
            ),
        )
    return entries
