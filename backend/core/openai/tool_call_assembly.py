"""SoAI - Tool-call assembly for streamed OpenAI payloads [backend/core/openai/tool_call_assembly.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Hashable
from typing import TYPE_CHECKING

from core.validation.integers import is_non_negative_strict_int
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "accumulate_tool_call",
    "finalize_tool_calls_sorted",
)


def accumulate_tool_call(
    tool_calls: dict[Hashable, JSONDict],
    call: JSONDict,
    *,
    sequence_index: int | None = None,
    content_index_before: int = 0,
    thinking_index_before: int = 0,
    thinking_duration_before_ms: int | None = None,
    explicit_content_index_before: bool = False,
    explicit_thinking_index_before: bool = False,
) -> None:
    if sequence_index is not None and sequence_index < 0:
        raise ValueError(
            "Tool call field 'sequence_index' must be a non-negative integer when provided.",
        )
    if content_index_before < 0:
        raise ValueError("Tool call field 'content_index_before' must be a non-negative integer.")
    if thinking_index_before < 0:
        raise ValueError("Tool call field 'thinking_index_before' must be a non-negative integer.")
    if thinking_duration_before_ms is not None and thinking_duration_before_ms < 0:
        raise ValueError(
            "Tool call field 'thinking_duration_before_ms' must be a non-negative integer.",
        )
    call_id = call.get("id")
    call_index = coerce_optional_non_negative_int_strict(call.get("index"))
    key: Hashable | None = None
    entry: JSONDict | None = None

    if isinstance(call_id, str) and call_id:
        key = call_id
        entry = tool_calls.get(call_id)
        if entry is None and call_index is not None:
            indexed_entry = tool_calls.get(call_index)
            if indexed_entry is not None:
                tool_calls[call_id] = indexed_entry
                del tool_calls[call_index]
                indexed_entry["_key"] = call_id
                entry = indexed_entry
        if entry is not None and call_index is not None:
            indexed_entry = tool_calls.get(call_index)
            if indexed_entry is not None and indexed_entry is not entry:
                indexed_entry_id = indexed_entry.get("id")
                if (
                    not isinstance(indexed_entry_id, str)
                    or not indexed_entry_id
                    or indexed_entry_id == call_id
                ):
                    del tool_calls[call_index]
    elif call_index is not None:
        key = call_index
        entry = tool_calls.get(call_index)
    else:
        return

    resolved_sequence_index: int
    if sequence_index is not None:
        resolved_sequence_index = sequence_index
    elif entry is not None:
        existing_sequence_index = entry.get("_sequence_index")
        if (
            isinstance(existing_sequence_index, bool)
            or not isinstance(existing_sequence_index, int)
            or existing_sequence_index < 0
        ):
            raise ValueError(
                "Tool call entry field '_sequence_index' must be a non-negative integer.",
            )
        resolved_sequence_index = existing_sequence_index
    elif call_index is not None:
        resolved_sequence_index = call_index
    else:
        raise ValueError(
            "Tool call field 'sequence_index' is required when call index is not available.",
        )

    if key is None:
        raise ValueError("Tool call key resolution failed.")

    if entry is None:
        entry = {
            "id": call_id,
            "type": call.get("type", "function"),
            "function": {"name": "", "arguments": ""},
            "_index": call_index,
            "_key": key,
            "_sequence_index": resolved_sequence_index,
            "_content_index_before": content_index_before,
            "_thinking_index_before": thinking_index_before,
            "_explicit_content_index_before": explicit_content_index_before,
            "_explicit_thinking_index_before": explicit_thinking_index_before,
        }
        tool_calls[key] = entry
    if explicit_content_index_before:
        entry["_content_index_before"] = content_index_before
        entry["_explicit_content_index_before"] = True
    if explicit_thinking_index_before:
        entry["_thinking_index_before"] = thinking_index_before
        entry["_explicit_thinking_index_before"] = True
    if thinking_duration_before_ms is not None and "_thinking_duration_before_ms" not in entry:
        entry["_thinking_duration_before_ms"] = thinking_duration_before_ms
    if isinstance(call_id, str) and call_id and (not entry.get("id")):
        entry["id"] = call_id
    if call_index is not None and entry.get("_index") is None:
        entry["_index"] = call_index
    function_payload = call.get("function")
    if isinstance(function_payload, dict):
        function_entry = entry.get("function")
        if not isinstance(function_entry, dict):
            function_entry = {"name": "", "arguments": ""}
            entry["function"] = function_entry
        name = function_payload.get("name")
        if isinstance(name, str) and name.strip():
            function_entry["name"] = name.strip()
        arguments = function_payload.get("arguments")
        if isinstance(arguments, str):
            existing_arguments = function_entry.get("arguments")
            if isinstance(existing_arguments, str):
                function_entry["arguments"] = existing_arguments + arguments
            else:
                function_entry["arguments"] = arguments


def _require_entry_integer(entry: JSONDict, key: str) -> int:
    value = entry.get(key)
    if not is_non_negative_strict_int(value):
        raise ValueError(f"Tool call entry field '{key}' must be a non-negative integer.")
    return value


def finalize_tool_calls_sorted(tool_calls: dict[Hashable, JSONDict]) -> list[JSONDict]:
    def sort_key(entry: JSONDict) -> tuple[int, bool, int]:
        sequence_index = _require_entry_integer(entry, "_sequence_index")
        index_value = entry.get("_index")
        if index_value is None:
            return (sequence_index, True, 0)
        if not is_non_negative_strict_int(index_value):
            raise ValueError(
                "Tool call entry field '_index' must be a non-negative integer when provided.",
            )
        return (sequence_index, False, index_value)

    entries = list(tool_calls.values())
    entries.sort(key=sort_key)
    finalized_calls: list[JSONDict] = []
    for entry in entries:
        tool_call: JSONDict = {
            "id": entry.get("id") or str(entry.get("_key", "")),
            "type": entry.get("type", "function"),
            "function": entry.get("function", {}),
            "sequence_index": _require_entry_integer(entry, "_sequence_index"),
            "content_index_before": _require_entry_integer(entry, "_content_index_before"),
            "thinking_index_before": _require_entry_integer(entry, "_thinking_index_before"),
        }
        thinking_duration_before_ms = coerce_optional_non_negative_int_strict(
            entry.get("_thinking_duration_before_ms"),
        )
        if thinking_duration_before_ms is not None:
            tool_call["thinking_duration_before_ms"] = thinking_duration_before_ms
        finalized_calls.append(tool_call)
    return finalized_calls
