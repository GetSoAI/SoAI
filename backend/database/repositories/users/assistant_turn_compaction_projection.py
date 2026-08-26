"""SoAI - Assistant-turn compaction projection helpers [backend/database/repositories/users/assistant_turn_compaction_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_POST_ASSISTANT_TEXT_FIELD,
    CONTEXT_COMPACTION_TOOL_NAME,
    is_context_compaction_active_completed_marker,
)
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "extract_post_compaction_assistant_text",
    "is_context_compaction_tool_call",
    "resolve_completed_compaction_marker",
    "resolve_context_compaction_marker",
)


def is_context_compaction_tool_call(tool_call: Mapping[str, JSONValue]) -> bool:
    tool_name_value = tool_call.get("tool_name")
    return (
        isinstance(tool_name_value, str) and tool_name_value.strip() == CONTEXT_COMPACTION_TOOL_NAME
    )


def resolve_context_compaction_marker(message_payload: JSONDict) -> JSONDict | None:
    return coerce_json_dict(message_payload.get("soai_compaction"))


def _resolve_timeline_tool_call_id(event: JSONDict) -> str:
    payload = coerce_json_dict(event.get("payload"))
    if payload is None:
        return ""
    tool = coerce_json_dict(payload.get("tool"))
    if tool is None:
        return ""
    call_id_value = tool.get("call_id")
    return call_id_value.strip() if isinstance(call_id_value, str) else ""


def extract_post_compaction_assistant_text(
    *,
    message_payload: JSONDict,
    compaction_call_id: str,
) -> str:
    projected_text = message_payload.get(CONTEXT_COMPACTION_POST_ASSISTANT_TEXT_FIELD)
    if isinstance(projected_text, str):
        return projected_text
    timeline_value = message_payload.get("assistant_event_timeline")
    if not isinstance(timeline_value, list):
        return ""
    after_compaction = False
    deltas: list[str] = []
    for event_value in timeline_value:
        if not isinstance(event_value, dict):
            continue
        event = dict(event_value)
        event_type_value = event.get("event_type")
        event_type = event_type_value.strip() if isinstance(event_type_value, str) else ""
        if after_compaction and event_type == "assistant_text_delta":
            payload = coerce_json_dict(event.get("payload"))
            if payload is not None:
                delta_value = payload.get("delta")
                if isinstance(delta_value, str):
                    deltas.append(delta_value)
            continue
        if event_type != "tool_call_completed":
            continue
        if _resolve_timeline_tool_call_id(event) == compaction_call_id:
            after_compaction = True
    return "".join(deltas)


def resolve_completed_compaction_marker(marker: JSONDict | None) -> JSONDict | None:
    if marker is None or not is_context_compaction_active_completed_marker(marker):
        return None
    sequence_index = marker.get("sequence_index")
    if (
        isinstance(sequence_index, bool)
        or not isinstance(sequence_index, int)
        or sequence_index < 0
    ):
        raise ValidationError("Compaction marker requires a non-negative sequence_index.")
    return dict(marker)
