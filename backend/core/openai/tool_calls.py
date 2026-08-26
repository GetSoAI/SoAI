"""SoAI - OpenAI tool call parsing/normalization helpers [backend/core/openai/tool_calls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.tool_call_text_lengths import resolve_message_text_lengths
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.tool_calls.chronology import (
    bound_required_chronology_anchor,
    resolve_content_index_before,
    resolve_explicit_call_chronology,
    resolve_optional_thinking_duration_before_ms,
    resolve_sequence_index,
    resolve_thinking_index_before,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "extract_tool_calls_from_payload",
    "normalize_tool_calls",
    "normalize_tool_calls_preserving_chronology",
    "resolve_normalized_tool_calls",
)


def _resolve_payload_tool_calls(message: JSONDict) -> list[JSONDict]:
    if "tool_calls" not in message:
        return []
    tool_calls = message.get("tool_calls")
    if tool_calls is None:
        return []
    if not isinstance(tool_calls, list):
        raise ValidationError("Tool call field 'tool_calls' must be a list when provided.")
    resolved_tool_calls: list[JSONDict] = []
    for call in tool_calls:
        if isinstance(call, dict):
            resolved_tool_calls.append(call)
    return resolved_tool_calls


def _normalize_tool_call_entries(raw_calls: list[JSONDict]) -> list[tuple[int, JSONDict]]:
    indexed_normalized: list[tuple[int, JSONDict]] = []
    seen_ids: set[str] = set()
    for call in raw_calls:
        if not isinstance(call, dict):
            continue
        call_id = call.get("id")
        call_id = str(call_id).strip() if call_id else ""
        function_payload_value = call.get("function")
        function_payload: JSONDict | None = (
            function_payload_value if isinstance(function_payload_value, dict) else None
        )
        call_name_value = call.get("name")
        name: str | None
        if isinstance(call_name_value, str):
            name = call_name_value
        elif function_payload is not None:
            function_name_value = function_payload.get("name")
            name = function_name_value if isinstance(function_name_value, str) else None
        else:
            name = None
        if "arguments" in call:
            arguments = call.get("arguments")
        elif function_payload is not None:
            arguments = function_payload.get("arguments")
        else:
            arguments = None
        name = name.strip() if isinstance(name, str) and name.strip() else ""
        if not call_id:
            call_id = create_prefixed_hex_id("call")
        if call_id in seen_ids:
            continue
        seen_ids.add(call_id)
        sequence_index = resolve_sequence_index(call)
        content_index_before = resolve_content_index_before(call)
        thinking_index_before = resolve_thinking_index_before(call)
        thinking_duration_before_ms = resolve_optional_thinking_duration_before_ms(call)
        indexed_item: JSONDict = {
            "id": call_id,
            "name": name,
            "arguments": arguments,
            "content_index_before": content_index_before,
            "thinking_index_before": thinking_index_before,
        }
        if thinking_duration_before_ms is not None:
            indexed_item["thinking_duration_before_ms"] = thinking_duration_before_ms
        indexed_normalized.append(
            (
                sequence_index,
                indexed_item,
            ),
        )
    indexed_normalized.sort(key=lambda item: item[0])
    return indexed_normalized


def normalize_tool_calls(raw_calls: list[JSONDict]) -> list[JSONDict]:
    indexed_normalized = _normalize_tool_call_entries(raw_calls)
    normalized: list[JSONDict] = []
    for contiguous_index, (_original_sequence_index, item) in enumerate(indexed_normalized):
        normalized_item: JSONDict = {
            "id": item["id"],
            "name": item["name"],
            "arguments": item["arguments"],
            "sequence_index": contiguous_index,
            "content_index_before": item["content_index_before"],
            "thinking_index_before": item["thinking_index_before"],
        }
        if "thinking_duration_before_ms" in item:
            normalized_item["thinking_duration_before_ms"] = item["thinking_duration_before_ms"]
        normalized.append(normalized_item)
    return normalized


def normalize_tool_calls_preserving_chronology(raw_calls: list[JSONDict]) -> list[JSONDict]:
    indexed_normalized = _normalize_tool_call_entries(raw_calls)
    normalized: list[JSONDict] = []
    for sequence_index, item in indexed_normalized:
        normalized_item: JSONDict = {
            "id": item["id"],
            "name": item["name"],
            "arguments": item["arguments"],
            "sequence_index": sequence_index,
            "content_index_before": item["content_index_before"],
            "thinking_index_before": item["thinking_index_before"],
        }
        if "thinking_duration_before_ms" in item:
            normalized_item["thinking_duration_before_ms"] = item["thinking_duration_before_ms"]
        normalized.append(normalized_item)
    return normalized


def resolve_normalized_tool_calls(
    raw_tool_calls: list[JSONDict],
) -> list[JSONDict]:
    return normalize_tool_calls(raw_tool_calls)


def extract_tool_calls_from_payload(payload: JSONValue) -> list[JSONDict]:
    if not isinstance(payload, dict):
        return []
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return []
    raw_calls: list[JSONDict] = []
    sequence_index = 0
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict):
            content_index_before, thinking_index_before = resolve_message_text_lengths(message)
            tool_calls = _resolve_payload_tool_calls(message)
            for call in tool_calls:
                call_with_chronology: JSONDict = dict(call)
                explicit_chronology = resolve_explicit_call_chronology(call)
                if explicit_chronology is None:
                    call_with_chronology["sequence_index"] = sequence_index
                    call_with_chronology["content_index_before"] = content_index_before
                    call_with_chronology["thinking_index_before"] = thinking_index_before
                    sequence_index += 1
                else:
                    (
                        explicit_sequence_index,
                        explicit_content_index_before,
                        explicit_thinking_index_before,
                    ) = explicit_chronology
                    call_with_chronology["sequence_index"] = explicit_sequence_index
                    call_with_chronology["content_index_before"] = bound_required_chronology_anchor(
                        explicit_content_index_before,
                        "content_index_before",
                        upper_bound=content_index_before,
                    )
                    call_with_chronology["thinking_index_before"] = (
                        bound_required_chronology_anchor(
                            explicit_thinking_index_before,
                            "thinking_index_before",
                            upper_bound=thinking_index_before,
                        )
                    )
                    if explicit_sequence_index >= sequence_index:
                        sequence_index = explicit_sequence_index + 1
                raw_calls.append(call_with_chronology)
    return normalize_tool_calls(raw_calls)
