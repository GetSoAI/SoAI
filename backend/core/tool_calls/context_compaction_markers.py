"""SoAI - Shared context compaction marker extraction [backend/core/tool_calls/context_compaction_markers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.assistant_timeline.tool_sequence_ownership import (
    register_tool_call_sequence_index_owner,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.serialization.json_parsing import parse_json_value
from core.tool_calls.context_compaction_prompt_message import (
    extract_context_compaction_prompt_message_from_result_payload,
    normalize_context_compaction_prompt_message,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
)
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_positive_strict_int, is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CONTEXT_COMPACTION_POST_ASSISTANT_TEXT_FIELD",
    "CONTEXT_COMPACTION_TOOL_NAME",
    "build_context_compaction_marker_from_tool_payload",
    "build_manual_context_compaction_call_id",
    "extract_context_compaction_marker_from_assistant_timeline",
    "extract_context_compaction_marker_from_message",
    "extract_context_compaction_markers_from_assistant_timeline",
    "extract_context_compaction_output_text_from_message",
    "extract_context_compaction_prompt_message_from_message",
    "is_context_compaction_active_completed_marker",
    "is_context_compaction_completed_marker",
    "is_context_compaction_removed_marker",
    "is_context_compaction_result_boundary_removed",
    "mark_context_compaction_result_boundary_removed",
)

CONTEXT_COMPACTION_TOOL_NAME = "context_compaction"
CONTEXT_COMPACTION_POST_ASSISTANT_TEXT_FIELD = "soai_post_compaction_assistant_text"
_VALID_CONTEXT_COMPACTION_STATUSES = frozenset(
    {
        TOOL_CALL_STATUS_COMPLETED,
        TOOL_CALL_STATUS_CANCELLED,
        TOOL_CALL_STATUS_ERROR,
    },
)
_BOUNDARY_REMOVED_AT_MS_FIELD = "boundary_removed_at_ms"
_BOUNDARY_REMOVED_REASON_FIELD = "boundary_removed_reason"


def build_manual_context_compaction_call_id(turn_id: str) -> str:
    return f"context_compaction:{turn_id}"


def _coerce_context_compaction_result_payload(value: JSONValue) -> JSONDict | None:
    if isinstance(value, str):
        try:
            parsed = parse_json_value(value, field="context compaction tool result")
        except ValidationError:
            return None
        return coerce_json_dict(normalize_for_json(parsed))
    return coerce_json_dict(normalize_for_json(value))


def _resolve_context_compaction_output_text(result_payload: JSONDict) -> str | None:
    output_value = result_payload.get("output")
    if not isinstance(output_value, str):
        return None
    output_text = output_value.strip()
    if not output_text:
        return None
    return output_text


def build_context_compaction_marker_from_tool_payload(
    tool_payload: JSONDict,
) -> JSONDict | None:
    tool_name_value = tool_payload.get("tool_name")
    tool_name = tool_name_value.strip() if isinstance(tool_name_value, str) else ""
    if tool_name != CONTEXT_COMPACTION_TOOL_NAME:
        return None
    status_value = tool_payload.get("status")
    status = status_value.strip() if isinstance(status_value, str) else ""
    if status not in _VALID_CONTEXT_COMPACTION_STATUSES:
        raise ValidationError("Context compaction tool payload requires a terminal status.")
    result_payload = _coerce_context_compaction_result_payload(tool_payload.get("result"))
    if result_payload is None:
        raise ValidationError("Context compaction tool payload requires a valid result payload.")
    compaction_details = coerce_json_dict(result_payload.get("compaction"))
    output_text = _resolve_context_compaction_output_text(result_payload)
    prompt_message = extract_context_compaction_prompt_message_from_result_payload(result_payload)
    call_id_value = tool_payload.get("call_id")
    call_id = (
        call_id_value.strip() if isinstance(call_id_value, str) and call_id_value.strip() else None
    )
    marker: JSONDict = {
        "tool_call_id": call_id,
        "status": status,
        "output": output_text,
    }
    if compaction_details is not None:
        trigger_value = compaction_details.get("trigger")
        trigger = (
            trigger_value.strip()
            if isinstance(trigger_value, str) and trigger_value.strip()
            else None
        )
        model_value = compaction_details.get("model")
        model = (
            model_value.strip() if isinstance(model_value, str) and model_value.strip() else None
        )
        marker["trigger"] = trigger
        marker["model"] = model
        marker["details"] = dict(compaction_details)
    if prompt_message is not None:
        marker["prompt_message"] = prompt_message
    if is_context_compaction_result_boundary_removed(result_payload):
        removed_at_ms = result_payload[_BOUNDARY_REMOVED_AT_MS_FIELD]
        if not is_strict_int(removed_at_ms):
            raise ValidationError("Context compaction boundary removal timestamp is invalid.")
        marker[_BOUNDARY_REMOVED_AT_MS_FIELD] = removed_at_ms
    removed_reason = result_payload.get(_BOUNDARY_REMOVED_REASON_FIELD)
    if isinstance(removed_reason, str) and removed_reason.strip():
        marker[_BOUNDARY_REMOVED_REASON_FIELD] = removed_reason.strip()
    return marker


def mark_context_compaction_result_boundary_removed(
    result_payload: JSONDict,
    *,
    removed_at_ms: int,
    reason: str,
) -> JSONDict:
    updated = dict(result_payload)
    updated[_BOUNDARY_REMOVED_AT_MS_FIELD] = int(removed_at_ms)
    updated[_BOUNDARY_REMOVED_REASON_FIELD] = str(reason)
    return updated


def is_context_compaction_result_boundary_removed(result_payload: JSONDict) -> bool:
    removed_at_ms = result_payload.get(_BOUNDARY_REMOVED_AT_MS_FIELD)
    if removed_at_ms is None:
        return False
    if not is_positive_strict_int(removed_at_ms):
        raise ValidationError("Context compaction boundary removal timestamp is invalid.")
    return True


def extract_context_compaction_marker_from_assistant_timeline(
    timeline: Sequence[JSONValue],
) -> JSONDict | None:
    markers = extract_context_compaction_markers_from_assistant_timeline(timeline)
    if not markers:
        return None
    return markers[-1]


def extract_context_compaction_markers_from_assistant_timeline(
    timeline: Sequence[JSONValue],
) -> list[JSONDict]:
    markers_by_sequence_index: dict[int, JSONDict] = {}
    sequence_owner_by_sequence_index: dict[int, str] = {}
    call_owner_by_call_id: dict[str, int] = {}
    completed_call_ids: set[str] = set()
    for event in timeline:
        event_dict = coerce_json_dict(event)
        if event_dict is None:
            continue
        event_type = event_dict.get("event_type")
        if event_type != "tool_call_completed":
            continue
        payload = coerce_json_dict(event_dict.get("payload"))
        if payload is None:
            raise ValidationError("Context compaction timeline entry requires a payload object.")
        tool = coerce_json_dict(payload.get("tool"))
        if tool is None:
            raise ValidationError(
                "Context compaction timeline entry requires a tool payload object.",
            )
        marker = build_context_compaction_marker_from_tool_payload(tool)
        if marker is None:
            continue
        call_id_value = marker.get("tool_call_id")
        call_id = (
            call_id_value.strip()
            if isinstance(call_id_value, str) and call_id_value.strip()
            else ""
        )
        sequence_index_value = tool.get("sequence_index")
        if (
            isinstance(sequence_index_value, bool)
            or not isinstance(sequence_index_value, int)
            or sequence_index_value < 0
        ):
            raise ValidationError(
                "Context compaction timeline entry requires a non-negative sequence_index.",
            )
        register_tool_call_sequence_index_owner(
            sequence_owner_by_sequence_index=sequence_owner_by_sequence_index,
            call_owner_by_call_id=call_owner_by_call_id,
            sequence_index=int(sequence_index_value),
            call_id=call_id,
            source="Context compaction timeline",
        )
        if call_id in completed_call_ids:
            raise ValidationError(
                f"Context compaction timeline contains duplicate completed entries for call_id '{call_id}'.",
            )
        completed_call_ids.add(call_id)
        marker["sequence_index"] = int(sequence_index_value)
        markers_by_sequence_index[int(sequence_index_value)] = marker
    return [markers_by_sequence_index[index] for index in sorted(markers_by_sequence_index)]


def extract_context_compaction_marker_from_message(
    message: Mapping[str, JSONValue],
) -> JSONDict | None:
    marker = coerce_json_dict(message.get("soai_compaction"))
    if marker is not None:
        return marker
    timeline_value = message.get("assistant_event_timeline")
    if not isinstance(timeline_value, list):
        return None
    return extract_context_compaction_marker_from_assistant_timeline(timeline_value)


def extract_context_compaction_output_text_from_message(
    message: Mapping[str, JSONValue],
) -> str | None:
    marker = extract_context_compaction_marker_from_message(message)
    if marker is None:
        return None
    output_value = marker.get("output")
    if not isinstance(output_value, str):
        return None
    output_text = output_value.strip()
    if not output_text:
        return None
    return output_text


def extract_context_compaction_prompt_message_from_message(
    message: Mapping[str, JSONValue],
) -> JSONDict | None:
    marker = extract_context_compaction_marker_from_message(message)
    if marker is None:
        return None
    return normalize_context_compaction_prompt_message(marker.get("prompt_message"))


def is_context_compaction_completed_marker(marker: JSONDict | None) -> bool:
    if marker is None:
        return False
    status_value = marker.get("status")
    return isinstance(status_value, str) and status_value.strip() == TOOL_CALL_STATUS_COMPLETED


def is_context_compaction_removed_marker(marker: JSONDict | None) -> bool:
    if marker is None:
        return False
    removed_at_ms = marker.get(_BOUNDARY_REMOVED_AT_MS_FIELD)
    if removed_at_ms is None:
        return False
    if not is_positive_strict_int(removed_at_ms):
        raise ValidationError("Context compaction boundary removal timestamp is invalid.")
    return True


def is_context_compaction_active_completed_marker(marker: JSONDict | None) -> bool:
    return is_context_compaction_completed_marker(
        marker,
    ) and not is_context_compaction_removed_marker(marker)
