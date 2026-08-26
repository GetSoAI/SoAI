"""SoAI - Agent tool-call protocol validation [backend/features/agent/runtime/tool_call_protocol_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.agent.tool_call_fields import (
    has_non_negative_tool_call_int,
    resolve_tool_call_name,
)
from core.mcp.tool_name_suggestions import (
    append_tool_suggestions_to_message,
    build_tool_name_candidates_from_entry_map,
    suggest_tool_names,
)
from core.openai.tool_call_arguments import normalize_openai_tool_call_arguments
from core.types.json import JSONDict, JSONValue
from features.agent.runtime.tool_argument_field_policy import (
    CONTENT_ARGUMENT_FIELD_KEYS,
    string_contains_internal_truncation_marker,
)

__all__ = (
    "ToolCallProtocolViolation",
    "validate_tool_call_protocol",
)

_INVALID_ARGUMENTS_CODE: str = "invalid_tool_arguments_json"
_INTERNAL_TRUNCATION_MARKER_CODE: str = "internal_truncation_marker_in_tool_arguments"
_TRUNCATED_TOOL_CALL_CODE: str = "truncated_tool_call_output"
_MISSING_TOOL_NAME_CODE: str = "missing_tool_call_name"
_UNAVAILABLE_TOOL_NAME_CODE: str = "unavailable_tool_call_name"


@dataclass(frozen=True, slots=True)
class ToolCallProtocolViolation:
    tool_name: str
    error_message: str
    received_argument_type: str
    signature: str
    prompt_tool_calls: list[JSONDict]
    prompt_tool_results: list[JSONValue]


def validate_tool_call_protocol(
    *,
    tool_calls: list[JSONDict],
    finish_reason: str | None,
    available_tool_map: dict[str, dict[str, JSONValue]],
) -> ToolCallProtocolViolation | None:
    if not tool_calls:
        return None
    if finish_reason == "length":
        return _build_batch_violation(
            tool_calls=tool_calls,
            primary_tool_call=tool_calls[0],
            code=_TRUNCATED_TOOL_CALL_CODE,
            error_message=(
                "The model output ended with finish_reason=length while tool calls were present. "
                "The tool-call payload may be incomplete, so it was not executed."
            ),
            received_argument_type="truncated",
        )
    for tool_call in tool_calls:
        tool_name = resolve_tool_call_name(tool_call)
        if not tool_name:
            return _build_batch_violation(
                tool_calls=tool_calls,
                primary_tool_call=tool_call,
                code=_MISSING_TOOL_NAME_CODE,
                error_message="Tool call name is required.",
                received_argument_type=_describe_argument_type(tool_call.get("arguments")),
            )
        if tool_name not in available_tool_map:
            suggestions = suggest_tool_names(
                tool_name,
                build_tool_name_candidates_from_entry_map(available_tool_map),
            )
            return _build_batch_violation(
                tool_calls=tool_calls,
                primary_tool_call=tool_call,
                code=_UNAVAILABLE_TOOL_NAME_CODE,
                error_message=append_tool_suggestions_to_message(
                    "Tool call name is not available in the current tool context.",
                    suggestions,
                ),
                received_argument_type=_describe_argument_type(tool_call.get("arguments")),
                suggested_tool_names=suggestions,
            )
        arguments_payload, _arguments_json, arguments_error = normalize_openai_tool_call_arguments(
            tool_call.get("arguments"),
        )
        if arguments_error is not None:
            return _build_batch_violation(
                tool_calls=tool_calls,
                primary_tool_call=tool_call,
                code=_INVALID_ARGUMENTS_CODE,
                error_message=arguments_error,
                received_argument_type=_describe_argument_type(tool_call.get("arguments")),
            )
        if arguments_payload is not None and _has_internal_marker_in_content_arguments(
            arguments_payload,
        ):
            return _build_batch_violation(
                tool_calls=tool_calls,
                primary_tool_call=tool_call,
                code=_INTERNAL_TRUNCATION_MARKER_CODE,
                error_message=(
                    "Tool arguments contain an internal SoAI context-compaction truncation "
                    "marker in an executable content field, so the tool call was not executed."
                ),
                received_argument_type="internal_truncation_marker",
            )
    return None


def _build_batch_violation(
    *,
    tool_calls: list[JSONDict],
    primary_tool_call: JSONDict,
    code: str,
    error_message: str,
    received_argument_type: str,
    suggested_tool_names: tuple[str, ...] = (),
) -> ToolCallProtocolViolation:
    prompt_tool_calls = [_build_prompt_tool_call(tool_call) for tool_call in tool_calls]
    prompt_tool_results: list[JSONValue] = [
        _build_rejected_tool_result(
            tool_call=tool_call,
            primary_tool_call=primary_tool_call,
            code=code,
            error_message=error_message,
            received_argument_type=received_argument_type,
            suggested_tool_names=suggested_tool_names,
        )
        for tool_call in tool_calls
    ]
    primary_tool_name = resolve_tool_call_name(primary_tool_call) or "tool"
    return ToolCallProtocolViolation(
        tool_name=primary_tool_name,
        error_message=error_message,
        received_argument_type=received_argument_type,
        signature=f"{code}:{primary_tool_name}:{received_argument_type}",
        prompt_tool_calls=prompt_tool_calls,
        prompt_tool_results=prompt_tool_results,
    )


def _build_prompt_tool_call(tool_call: JSONDict) -> JSONDict:
    prompt_tool_call: JSONDict = {
        "id": str(tool_call.get("id") or ""),
        "name": resolve_tool_call_name(tool_call) or "tool",
        "arguments": {},
    }
    sequence_index = tool_call.get("sequence_index")
    if has_non_negative_tool_call_int(sequence_index):
        prompt_tool_call["sequence_index"] = sequence_index
    content_index_before = tool_call.get("content_index_before")
    if has_non_negative_tool_call_int(content_index_before):
        prompt_tool_call["content_index_before"] = content_index_before
    thinking_index_before = tool_call.get("thinking_index_before")
    if has_non_negative_tool_call_int(thinking_index_before):
        prompt_tool_call["thinking_index_before"] = thinking_index_before
    thinking_duration_before_ms = tool_call.get("thinking_duration_before_ms")
    if has_non_negative_tool_call_int(thinking_duration_before_ms):
        prompt_tool_call["thinking_duration_before_ms"] = thinking_duration_before_ms
    return prompt_tool_call


def _build_rejected_tool_result(
    *,
    tool_call: JSONDict,
    primary_tool_call: JSONDict,
    code: str,
    error_message: str,
    received_argument_type: str,
    suggested_tool_names: tuple[str, ...],
) -> JSONDict:
    if str(tool_call.get("id") or "") != str(primary_tool_call.get("id") or ""):
        return {
            "error": (
                "Tool call skipped because another tool call in the same assistant message "
                "violated the tool-call protocol."
            ),
            "code": "tool_call_batch_rejected",
            "tool_name": resolve_tool_call_name(tool_call) or "tool",
            "rejected_tool_name": resolve_tool_call_name(primary_tool_call) or "tool",
            "raw_arguments_omitted": True,
        }
    result_payload: JSONDict = {
        "error": error_message,
        "code": code,
        "tool_name": resolve_tool_call_name(tool_call) or "tool",
        "received_argument_type": received_argument_type,
        "required_shape": "function.arguments must be one JSON object matching the tool schema.",
        "raw_arguments_omitted": True,
    }
    if suggested_tool_names:
        result_payload["suggested_tool_names"] = list(suggested_tool_names)
    return result_payload


def _describe_argument_type(value: JSONValue | None) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "non_json"


def _has_internal_marker_in_content_arguments(
    value: JSONValue,
    *,
    key_name: str | None = None,
) -> bool:
    if isinstance(value, str):
        if key_name not in CONTENT_ARGUMENT_FIELD_KEYS:
            return False
        return string_contains_internal_truncation_marker(value)
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            if _has_internal_marker_in_content_arguments(item, key_name=key):
                return True
        return False
    if isinstance(value, list):
        for item in value:
            if _has_internal_marker_in_content_arguments(item, key_name=key_name):
                return True
        return False
    return False
