"""SoAI - Canonical assistant-turn prompt history projection [backend/database/repositories/users/assistant_turn_history_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.assistant_timeline.tool_sequence_ownership import (
    register_tool_call_sequence_index_owner,
)
from core.errors.exceptions import ValidationError
from core.openai.tool_call_arguments import (
    serialize_openai_tool_call_arguments_for_prompt,
)
from core.serialization.json import serialize_json_compact_stable
from core.tool_calls.status_values import (
    is_terminal_tool_call_status,
    resolve_terminal_tool_call_payload,
)
from core.validation.integers import is_strict_int
from database.repositories.users.assistant_turn_compaction_projection import (
    extract_post_compaction_assistant_text,
    is_context_compaction_tool_call,
    resolve_completed_compaction_marker,
    resolve_context_compaction_marker,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_visible_history_message",
    "project_assistant_turn_history_messages",
)


def _has_message_content(content: JSONValue) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return bool(content)
    return content is not None


def _resolve_non_negative_int(value: JSONValue, *, source: str) -> int:
    if not is_strict_int(value) or value < 0:
        raise ValidationError(f"{source} must be a non-negative integer.")
    return int(value)


def _resolve_call_id(tool_call: Mapping[str, JSONValue], *, source: str) -> str:
    call_id_value = tool_call.get("call_id")
    call_id = (
        call_id_value.strip() if isinstance(call_id_value, str) and call_id_value.strip() else ""
    )
    if not call_id:
        raise ValidationError(f"{source} requires a call_id.")
    return call_id


def build_visible_history_message(message_payload: JSONDict) -> JSONDict:
    visible_message: JSONDict = {
        "role": str(message_payload.get("role") or ""),
        "content": message_payload.get("content", ""),
    }
    timestamp_value = message_payload.get("timestamp")
    if is_strict_int(timestamp_value):
        visible_message["timestamp"] = int(timestamp_value)
    return visible_message


def _build_compaction_marker_message(
    message_payload: JSONDict,
    marker: JSONDict,
) -> JSONDict:
    marker_message = build_visible_history_message(message_payload)
    marker_message["content"] = ""
    marker_message["soai_compaction"] = dict(marker)
    return marker_message


def _build_tool_call_message(tool_call: Mapping[str, JSONValue]) -> JSONDict:
    message: JSONDict = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": str(tool_call.get("call_id") or ""),
                "type": "function",
                "function": {
                    "name": str(tool_call.get("tool_name") or ""),
                    "arguments": serialize_openai_tool_call_arguments_for_prompt(
                        tool_call.get("arguments"),
                    ),
                },
            },
        ],
    }
    assistant_at_ms = tool_call.get("assistant_at_ms")
    if is_strict_int(assistant_at_ms):
        message["timestamp"] = int(assistant_at_ms)
    return message


def _build_tool_result_content(tool_call: Mapping[str, JSONValue]) -> str:
    return serialize_json_compact_stable(resolve_terminal_tool_call_payload(dict(tool_call)))


def _build_tool_result_message(tool_call: Mapping[str, JSONValue]) -> JSONDict:
    message: JSONDict = {
        "role": "tool",
        "tool_call_id": str(tool_call.get("call_id") or ""),
        "content": _build_tool_result_content(tool_call),
    }
    assistant_at_ms = tool_call.get("assistant_at_ms")
    if is_strict_int(assistant_at_ms):
        message["timestamp"] = int(assistant_at_ms)
    return message


def _build_post_compaction_visible_message(
    message_payload: JSONDict,
    compaction_call_id: str,
) -> JSONDict | None:
    content = extract_post_compaction_assistant_text(
        message_payload=message_payload,
        compaction_call_id=compaction_call_id,
    )
    if not content.strip():
        return None
    visible_message = build_visible_history_message(message_payload)
    visible_message["content"] = content
    return visible_message


def project_assistant_turn_history_messages(
    *,
    message_payload: JSONDict,
    anchored_tool_calls: Sequence[JSONDict],
) -> list[JSONDict]:
    projected_messages: list[JSONDict] = []
    sequence_entries: list[tuple[int, str, JSONDict]] = []
    sequence_owner_by_sequence_index: dict[int, str] = {}
    call_owner_by_call_id: dict[str, int] = {}
    compaction_call_id_by_sequence_index: dict[int, str] = {}
    seen_call_ids: set[str] = set()
    context_compaction_marker = resolve_context_compaction_marker(message_payload)
    completed_compaction_marker = resolve_completed_compaction_marker(context_compaction_marker)
    completed_compaction_call_id = ""
    compaction_tool_call_present = False
    for tool_call in anchored_tool_calls:
        status_value = tool_call.get("status")
        status = status_value.strip() if isinstance(status_value, str) else ""
        if not is_terminal_tool_call_status(status):
            continue
        sequence_index = _resolve_non_negative_int(
            tool_call.get("sequence_index"),
            source="Canonical assistant turn tool sequence_index",
        )
        call_id = _resolve_call_id(tool_call, source="Canonical assistant turn tool call")
        if call_id in seen_call_ids:
            raise ValidationError(
                f"Canonical assistant turn contains duplicate tool call_id '{call_id}'.",
            )
        seen_call_ids.add(call_id)
        if is_context_compaction_tool_call(tool_call):
            compaction_tool_call_present = True
            compaction_call_id_by_sequence_index[sequence_index] = call_id
            continue
        register_tool_call_sequence_index_owner(
            sequence_owner_by_sequence_index=sequence_owner_by_sequence_index,
            call_owner_by_call_id=call_owner_by_call_id,
            sequence_index=sequence_index,
            call_id=call_id,
            source="Canonical assistant turn",
        )
        sequence_entries.append((sequence_index, "tool", dict(tool_call)))
    if completed_compaction_marker is not None:
        marker_sequence_index = _resolve_non_negative_int(
            completed_compaction_marker.get("sequence_index"),
            source="Canonical assistant turn compaction sequence_index",
        )
        marker_call_id_value = completed_compaction_marker.get("call_id")
        if marker_call_id_value is None:
            marker_call_id_value = completed_compaction_marker.get("tool_call_id")
        marker_call_id = (
            marker_call_id_value.strip()
            if isinstance(marker_call_id_value, str) and marker_call_id_value.strip()
            else ""
        )
        if not marker_call_id:
            if not compaction_tool_call_present:
                raise ValidationError(
                    "Canonical assistant turn compaction marker requires a call_id.",
                )
            marker_call_id = compaction_call_id_by_sequence_index.get(
                marker_sequence_index,
                "",
            )
        if not marker_call_id:
            raise ValidationError("Canonical assistant turn compaction marker requires a call_id.")
        completed_compaction_call_id = marker_call_id
        register_tool_call_sequence_index_owner(
            sequence_owner_by_sequence_index=sequence_owner_by_sequence_index,
            call_owner_by_call_id=call_owner_by_call_id,
            sequence_index=marker_sequence_index,
            call_id=marker_call_id,
            source="Canonical assistant turn",
        )
        sequence_entries.append((marker_sequence_index, "compaction", completed_compaction_marker))
    sequence_entries.sort(key=lambda item: item[0])
    for _sequence_index, entry_type, entry_payload in sequence_entries:
        if entry_type == "compaction":
            projected_messages.append(
                _build_compaction_marker_message(message_payload, entry_payload),
            )
            continue
        projected_messages.append(_build_tool_call_message(entry_payload))
        projected_messages.append(_build_tool_result_message(entry_payload))
    visible_message = build_visible_history_message(message_payload)
    if completed_compaction_marker is None:
        if _has_message_content(visible_message.get("content")):
            projected_messages.append(visible_message)
    else:
        post_compaction_message = _build_post_compaction_visible_message(
            message_payload,
            completed_compaction_call_id,
        )
        if post_compaction_message is not None:
            projected_messages.append(post_compaction_message)
    return projected_messages
