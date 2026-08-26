"""SoAI - Tool-call availability error handling [backend/orchestrator/tool_calls/execution_availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.tool_name_suggestions import (
    append_tool_suggestions_to_message,
    build_tool_name_candidates_from_entry_map,
    suggest_tool_names,
)
from core.tool_calls.error_payloads import build_tool_call_error_payload
from orchestrator.tool_calls.execution_persistence import (
    persist_tool_call_invalid_tool_error,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from orchestrator.tool_calls.persistence import (
        ToolCallExecutionRecord,
        ToolCallPersistenceContext,
    )

__all__ = ("persist_unavailable_tool_call_error",)


def build_unavailable_tool_result_payload(
    *,
    error_message: str,
    suggested_tool_names: tuple[str, ...],
) -> JSONDict:
    result_payload = build_tool_call_error_payload(
        error_message=error_message,
        code="unavailable_tool_call_name",
    )
    if suggested_tool_names:
        result_payload["suggested_tool_names"] = list(suggested_tool_names)
    return result_payload


async def persist_unavailable_tool_call_error(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    tool_name: str,
    tool_map: dict[str, dict[str, JSONValue]],
) -> JSONDict:
    suggestions = suggest_tool_names(
        tool_name,
        build_tool_name_candidates_from_entry_map(tool_map),
    )
    availability_error_message = append_tool_suggestions_to_message(
        "MCP tool is not available for this conversation.",
        suggestions,
    )
    return await persist_tool_call_invalid_tool_error(
        persistence_context,
        record=record,
        result_payload=build_unavailable_tool_result_payload(
            error_message=availability_error_message,
            suggested_tool_names=suggestions,
        ),
    )
