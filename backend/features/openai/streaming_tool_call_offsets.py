"""SoAI - Shared OpenAI streaming tool call offsets [backend/features/openai/streaming_tool_call_offsets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.chronology import offset_required_chronology_anchor
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("apply_collected_tool_call_offsets",)


def apply_collected_tool_call_offsets(
    *,
    collected_tool_calls: list[JSONDict],
    tool_sequence_offset: int,
    content_index_base: int,
    thinking_index_base: int,
    content_index_upper_bound: int,
    thinking_index_upper_bound: int,
) -> int:
    for call in collected_tool_calls:
        sequence_index_value = call.get("sequence_index")
        if is_strict_int(sequence_index_value):
            call["sequence_index"] = tool_sequence_offset + int(sequence_index_value)
        content_index_before_value = call.get("content_index_before")
        if is_strict_int(content_index_before_value):
            call["content_index_before"] = offset_required_chronology_anchor(
                content_index_before_value,
                "content_index_before",
                offset=content_index_base,
                upper_bound=content_index_upper_bound,
            )
        thinking_index_before_value = call.get("thinking_index_before")
        if is_strict_int(thinking_index_before_value):
            call["thinking_index_before"] = offset_required_chronology_anchor(
                thinking_index_before_value,
                "thinking_index_before",
                offset=thinking_index_base,
                upper_bound=thinking_index_upper_bound,
            )
    return tool_sequence_offset + len(collected_tool_calls)
