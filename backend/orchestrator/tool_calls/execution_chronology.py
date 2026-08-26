"""SoAI - Tool call execution chronology resolution [backend/orchestrator/tool_calls/execution_chronology.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.chronology import (
    resolve_optional_non_negative_integer,
    resolve_required_non_negative_integer,
)
from orchestrator.tool_calls.persistence import ToolCallChronology

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resolve_tool_call_execution_chronology",)


def resolve_tool_call_execution_chronology(tool_call: JSONDict) -> ToolCallChronology:
    return ToolCallChronology(
        sequence_index=resolve_required_non_negative_integer(
            tool_call.get("sequence_index"),
            "sequence_index",
            field_label="Tool call",
            exception_type=ValueError,
        ),
        content_index_before=resolve_required_non_negative_integer(
            tool_call.get("content_index_before"),
            "content_index_before",
            field_label="Tool call",
            exception_type=ValueError,
        ),
        thinking_index_before=resolve_required_non_negative_integer(
            tool_call.get("thinking_index_before"),
            "thinking_index_before",
            field_label="Tool call",
            exception_type=ValueError,
        ),
        thinking_duration_before_ms=resolve_optional_non_negative_integer(
            tool_call.get("thinking_duration_before_ms"),
            "thinking_duration_before_ms",
            field_label="Tool call",
            exception_type=ValueError,
        ),
    )
