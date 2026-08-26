"""SoAI - Tool call sequence assignment policy [backend/orchestrator/tool_calls/sequence_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.openai.tool_calls import resolve_normalized_tool_calls
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ToolCallSequenceAssignment",
    "assign_tool_call_sequences",
)


@dataclass(frozen=True, slots=True)
class ToolCallSequenceAssignment:
    calls: list[JSONDict]
    existing_by_call_id: dict[str, JSONDict]


def assign_tool_call_sequences(
    *,
    raw_tool_calls: list[JSONDict],
    existing_calls: list[JSONDict],
) -> ToolCallSequenceAssignment:
    normalized_calls = resolve_normalized_tool_calls(raw_tool_calls)
    if not normalized_calls:
        return ToolCallSequenceAssignment(calls=[], existing_by_call_id={})
    existing_sequence = _load_existing_sequence(existing_calls)
    next_sequence_index = len(existing_calls)
    assigned_sequence_by_call_id = dict(existing_sequence.sequence_by_call_id)
    for tool_call in normalized_calls:
        assigned_sequence_index = _resolve_sequence_index_for_call(
            tool_call=tool_call,
            assigned_sequence_by_call_id=assigned_sequence_by_call_id,
            next_sequence_index=next_sequence_index,
        )
        if assigned_sequence_index == next_sequence_index:
            next_sequence_index += 1
        tool_call["sequence_index"] = assigned_sequence_index
    _repair_new_duplicate_sequence_indexes(
        normalized_calls=normalized_calls,
        existing_sequence_by_call_id=existing_sequence.sequence_by_call_id,
        next_sequence_index=next_sequence_index,
    )
    return ToolCallSequenceAssignment(
        calls=normalized_calls,
        existing_by_call_id=existing_sequence.existing_by_call_id,
    )


@dataclass(frozen=True, slots=True)
class _ExistingToolCallSequence:
    sequence_by_call_id: dict[str, int]
    existing_by_call_id: dict[str, JSONDict]


def _load_existing_sequence(existing_calls: list[JSONDict]) -> _ExistingToolCallSequence:
    existing_by_call_id: dict[str, JSONDict] = {}
    sequence_by_call_id: dict[str, int] = {}
    sequence_indexes: list[int] = []
    for existing in existing_calls:
        sequence_value = existing.get("sequence_index")
        if not is_strict_int(sequence_value):
            continue
        sequence_indexes.append(sequence_value)
        call_id = _read_storage_call_id(existing)
        if call_id and call_id not in sequence_by_call_id:
            sequence_by_call_id[call_id] = sequence_value
            existing_by_call_id[call_id] = existing
    _validate_existing_sequence(sequence_indexes, expected_count=len(existing_calls))
    return _ExistingToolCallSequence(
        sequence_by_call_id=sequence_by_call_id,
        existing_by_call_id=existing_by_call_id,
    )


def _validate_existing_sequence(sequence_indexes: list[int], *, expected_count: int) -> None:
    if not sequence_indexes:
        return
    unique_sequence_indexes = set(sequence_indexes)
    if len(unique_sequence_indexes) != len(sequence_indexes):
        raise StateError("Tool call sequence_index contains duplicates for a message.")
    if min(unique_sequence_indexes) != 0:
        raise StateError("Tool call sequence_index must start at 0 for a message.")
    if max(unique_sequence_indexes) + 1 != len(unique_sequence_indexes):
        raise StateError("Tool call sequence_index must be contiguous for a message.")
    if len(unique_sequence_indexes) != expected_count:
        raise StateError("Tool call rows could not be validated for contiguous sequence_index.")


def _resolve_sequence_index_for_call(
    *,
    tool_call: JSONDict,
    assigned_sequence_by_call_id: dict[str, int],
    next_sequence_index: int,
) -> int:
    call_id = _read_call_id(tool_call)
    if not call_id:
        return next_sequence_index
    existing_sequence = assigned_sequence_by_call_id.get(call_id)
    if existing_sequence is not None:
        return existing_sequence
    assigned_sequence_by_call_id[call_id] = next_sequence_index
    return next_sequence_index


def _repair_new_duplicate_sequence_indexes(
    *,
    normalized_calls: list[JSONDict],
    existing_sequence_by_call_id: dict[str, int],
    next_sequence_index: int,
) -> None:
    used_sequence_indexes: set[int] = set()
    for tool_call in normalized_calls:
        sequence_value = tool_call.get("sequence_index")
        sequence_index = sequence_value if is_strict_int(sequence_value) else None
        if sequence_index is None:
            continue
        if sequence_index not in used_sequence_indexes:
            used_sequence_indexes.add(sequence_index)
            continue
        call_id = _read_call_id(tool_call)
        if call_id and call_id in existing_sequence_by_call_id:
            raise StateError(
                "Tool call sequence assignment produced a duplicate fixed sequence_index.",
            )
        while next_sequence_index in used_sequence_indexes:
            next_sequence_index += 1
        tool_call["sequence_index"] = next_sequence_index
        used_sequence_indexes.add(next_sequence_index)
        next_sequence_index += 1


def _read_call_id(tool_call: JSONDict) -> str:
    call_id_value = tool_call.get("id")
    return call_id_value.strip() if isinstance(call_id_value, str) else ""


def _read_storage_call_id(tool_call: JSONDict) -> str:
    call_id_value = tool_call.get("call_id")
    return call_id_value.strip() if isinstance(call_id_value, str) else ""
