"""SoAI - Agent assistant-message tool sequence indexing [backend/features/agent/runtime/tool_sequence_indexing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import JSONDict
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = (
    "apply_tool_sequence_offset",
    "resolve_next_tool_sequence_index",
)


def resolve_next_tool_sequence_index(
    *,
    activities: Iterable[JSONDict],
    tool_calls: Iterable[JSONDict],
) -> int:
    max_sequence_index = -1
    for entry in activities:
        max_sequence_index = max(max_sequence_index, _read_sequence_index(entry))
    for entry in tool_calls:
        max_sequence_index = max(max_sequence_index, _read_sequence_index(entry))
    return max_sequence_index + 1


def apply_tool_sequence_offset(
    *,
    tool_calls: list[JSONDict],
    next_sequence_index: int,
) -> int:
    offset = max(0, int(next_sequence_index))
    max_sequence_index = offset - 1
    for tool_call in tool_calls:
        sequence_index = _read_sequence_index(tool_call)
        if sequence_index < 0:
            continue
        resolved_sequence_index = offset + sequence_index
        tool_call["sequence_index"] = resolved_sequence_index
        max_sequence_index = max(max_sequence_index, resolved_sequence_index)
    return max_sequence_index + 1


def _read_sequence_index(value: JSONDict) -> int:
    sequence_index = value.get("sequence_index")
    if is_strict_int(sequence_index):
        return max(0, sequence_index)
    return -1
