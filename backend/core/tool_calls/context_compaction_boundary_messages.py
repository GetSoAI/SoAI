"""SoAI - Context compaction boundary message projection [backend/core/tool_calls/context_compaction_boundary_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.openai.message_fields import OPENAI_MESSAGE_FIELDS_COMMON
from core.openai.pinned_prefix import split_leading_pinned_prefix
from core.serialization.json import normalize_for_json
from core.tool_calls.compaction_projections import normalize_boundary_projections
from core.tool_calls.compaction_timeline_boundaries import (
    normalize_timeline_boundary_entries,
)
from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_TOOL_NAME,
    extract_context_compaction_marker_from_message,
)
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("normalize_context_compaction_boundary_messages",)

_BOUNDARY_RELEVANT_MESSAGE_FIELDS: frozenset[str] = OPENAI_MESSAGE_FIELDS_COMMON
_BOUNDARY_TEXT_MESSAGE_FIELDS: frozenset[str] = frozenset(
    (
        "role",
        "content",
        "name",
        "refusal",
        "audio",
    ),
)


def _normalize_boundary_text_message(message: JSONDict) -> JSONDict | None:
    normalized = coerce_json_dict(
        normalize_for_json(
            {
                key: value
                for key, value in message.items()
                if key in _BOUNDARY_RELEVANT_MESSAGE_FIELDS
            },
        ),
    )
    if normalized is None:
        return None
    payload: JSONDict = {}
    for field_name, value in normalized.items():
        if field_name not in _BOUNDARY_TEXT_MESSAGE_FIELDS:
            continue
        payload[field_name] = value
    role_value = payload.get("role")
    role = role_value.strip() if isinstance(role_value, str) else ""
    content_value = payload.get("content")
    if role == "assistant" and content_value in ("", [], None):
        return None
    return payload or None


def _build_boundary_tool_call_entry(
    *,
    call_id: str,
    tool_name: str,
) -> JSONDict:
    return {
        "soai_boundary_type": "tool_call",
        "tool_call_id": call_id,
        "tool_name": tool_name,
    }


def _build_boundary_tool_result_entry(
    *,
    call_id: str,
) -> JSONDict:
    return {
        "soai_boundary_type": "tool_result",
        "tool_call_id": call_id,
    }


def _normalize_boundary_tool_call_entries(message: JSONDict) -> list[JSONDict]:
    role_value = message.get("role")
    role = role_value.strip() if isinstance(role_value, str) else ""
    if role != "assistant":
        return []
    tool_calls_value = message.get("tool_calls")
    if not isinstance(tool_calls_value, list):
        return []
    entries: list[JSONDict] = []
    for tool_call in tool_calls_value:
        tool_call_dict = coerce_json_dict(normalize_for_json(tool_call))
        if tool_call_dict is None:
            continue
        call_id_value = tool_call_dict.get("id")
        tool_call_id = (
            call_id_value.strip()
            if isinstance(call_id_value, str) and call_id_value.strip()
            else ""
        )
        function_dict = coerce_json_dict(tool_call_dict.get("function"))
        tool_name_value = function_dict.get("name") if function_dict is not None else None
        tool_name = (
            tool_name_value.strip()
            if isinstance(tool_name_value, str) and tool_name_value.strip()
            else ""
        )
        if not tool_call_id or not tool_name or tool_name == CONTEXT_COMPACTION_TOOL_NAME:
            continue
        entries.append(
            _build_boundary_tool_call_entry(
                call_id=tool_call_id,
                tool_name=tool_name,
            ),
        )
    return entries


def _normalize_boundary_tool_result_entry(message: JSONDict) -> JSONDict | None:
    role_value = message.get("role")
    role = role_value.strip() if isinstance(role_value, str) else ""
    if role != "tool":
        return None
    tool_call_id_value = message.get("tool_call_id")
    tool_call_id = (
        tool_call_id_value.strip()
        if isinstance(tool_call_id_value, str) and tool_call_id_value.strip()
        else ""
    )
    if not tool_call_id:
        return None
    return _build_boundary_tool_result_entry(
        call_id=tool_call_id,
    )


def _append_text_message(entries: list[JSONDict], message: JSONDict) -> list[JSONDict]:
    normalized_text_message = _normalize_boundary_text_message(message)
    if normalized_text_message is not None:
        return [*entries, normalized_text_message]
    return entries


def _normalize_boundary_entries_for_message(message: JSONDict) -> list[JSONDict]:
    has_projection = isinstance(message.get("tool_call_projections"), list)
    marker = (
        extract_context_compaction_marker_from_message(message)
        if "soai_compaction" in message or not has_projection
        else None
    )
    if marker is not None:
        return []
    tool_call_entries = _normalize_boundary_tool_call_entries(message)
    if tool_call_entries:
        return _append_text_message(tool_call_entries, message)
    tool_projection_entries = normalize_boundary_projections(message)
    if tool_projection_entries:
        return _append_text_message(tool_projection_entries, message)
    timeline_entries = normalize_timeline_boundary_entries(message)
    if timeline_entries:
        return _append_text_message(timeline_entries, message)
    tool_result_entry = _normalize_boundary_tool_result_entry(message)
    if tool_result_entry is not None:
        return [tool_result_entry]
    normalized_text_message = _normalize_boundary_text_message(message)
    return [normalized_text_message] if normalized_text_message is not None else []


def normalize_context_compaction_boundary_messages(
    messages: Sequence[JSONDict],
    *,
    strip_leading_pinned_prefix: bool,
) -> list[JSONDict]:
    normalized_messages: list[JSONDict] = []
    for message in messages:
        normalized_messages.extend(_normalize_boundary_entries_for_message(message))
    if not strip_leading_pinned_prefix:
        return normalized_messages
    remaining_messages = split_leading_pinned_prefix(normalized_messages)[1]
    return remaining_messages
