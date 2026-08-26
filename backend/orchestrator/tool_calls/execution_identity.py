"""SoAI - Tool call executor identity resolution [backend/orchestrator/tool_calls/execution_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import StateError
from core.orchestrator.types import MCPToolContext
from orchestrator.tool_calls.persistence import ToolCallChronology

__all__ = (
    "ToolCallExecutorIdentity",
    "resolve_tool_call_executor_identity",
)


@dataclass(frozen=True, slots=True)
class ToolCallExecutorIdentity:
    assistant_at_ms: int
    assistant_turn_at_ms: int
    model_variant_index: int
    sequence_index: int
    content_index_before: int
    thinking_index_before: int


def resolve_tool_call_executor_identity(
    *,
    tool_context: MCPToolContext,
    chronology: ToolCallChronology,
) -> ToolCallExecutorIdentity:
    assistant_at_ms = tool_context.assistant_at_ms
    assistant_turn_at_ms = tool_context.assistant_turn_at_ms
    model_variant_index = tool_context.model_variant_index
    if assistant_at_ms is None or assistant_turn_at_ms is None or model_variant_index is None:
        raise StateError("Tool call execution requires assistant turn identity.")
    return ToolCallExecutorIdentity(
        assistant_at_ms=assistant_at_ms,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        sequence_index=chronology.sequence_index,
        content_index_before=chronology.content_index_before,
        thinking_index_before=chronology.thinking_index_before,
    )
