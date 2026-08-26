"""SoAI - Agent tool-call execution support [backend/features/agent/runtime/tool_call_execution_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.tool_call_arguments import normalize_openai_tool_call_arguments
from core.tool_calls.status_values import resolve_tool_call_status_from_result_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AgentToolCallExecutionOutcome",
    "AgentToolCallPostprocessContext",
    "AgentToolCallPostprocessResult",
    "coerce_in_progress_tool_result_to_error",
    "resolve_tool_completion_status",
    "serialize_tool_arguments_for_event",
)


def resolve_tool_completion_status(result_payload: JSONValue) -> str:
    return resolve_tool_call_status_from_result_payload(result_payload)


def serialize_tool_arguments_for_event(tool_call: JSONDict) -> str | None:
    _arguments_payload, arguments_json, _arguments_error = normalize_openai_tool_call_arguments(
        tool_call.get("arguments"),
    )
    return arguments_json


def coerce_in_progress_tool_result_to_error(result_payload: JSONValue) -> JSONValue:
    if not isinstance(result_payload, dict):
        return result_payload
    code_value = result_payload.get("code")
    code_text = code_value.strip().lower() if isinstance(code_value, str) else ""
    if code_text != "in_progress":
        return dict(result_payload)
    return {
        "error": "Tool call returned an in_progress result, which is not supported in agent turns.",
        "code": "server_error",
    }


@dataclass(frozen=True, slots=True)
class AgentToolCallPostprocessContext:
    tool_call_id: str
    tool_name: str
    tool_arguments: str | None
    completion_sequence: int
    result_payload: JSONDict
    code_diffs: list[JSONDict] | None


@dataclass(frozen=True, slots=True)
class AgentToolCallPostprocessResult:
    result_payload: JSONDict
    code_diffs: list[JSONDict] | None
    todo_updated: bool = False
    todo_revision: int | None = None
    todo: list[dict[str, JSONValue]] | None = None
    todo_explanation: str | None = None
    plan_updated: bool = False
    plan_revision: int | None = None
    plan_title: str | None = None
    plan_markdown: str | None = None


@dataclass(frozen=True, slots=True)
class AgentToolCallExecutionOutcome:
    tool_call_id: str
    tool_name: str
    tool_arguments: str | None
    started_at_ms: int
    duration_ms: int
    result_payload: JSONValue
    code_diffs: list[JSONDict] | None
