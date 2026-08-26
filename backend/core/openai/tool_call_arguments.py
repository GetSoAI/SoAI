"""SoAI - OpenAI tool-call argument serialization helpers [backend/core/openai/tool_call_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "normalize_openai_tool_call_arguments",
    "serialize_openai_tool_call_arguments_for_prompt",
    "should_sanitize_openai_tool_call_arguments",
)


def serialize_openai_tool_call_arguments_for_prompt(raw_arguments: JSONValue) -> str:
    _arguments_payload, arguments_json, arguments_error = normalize_openai_tool_call_arguments(
        raw_arguments,
    )
    if arguments_error is None:
        return arguments_json
    return "{}"


def should_sanitize_openai_tool_call_arguments(raw_arguments: JSONValue) -> bool:
    if raw_arguments is None:
        return False
    if isinstance(raw_arguments, str):
        if not raw_arguments.strip():
            return True
        try:
            parsed = parse_json_value(raw_arguments)
        except ValidationError:
            return True
        return not isinstance(parsed, dict)
    return not isinstance(raw_arguments, dict)


def normalize_openai_tool_call_arguments(
    raw_arguments: JSONValue,
) -> tuple[JSONDict | None, str, str | None]:
    if raw_arguments is None:
        return (None, "{}", "Tool arguments are required.")
    if isinstance(raw_arguments, dict):
        arguments_dict: JSONDict = dict(raw_arguments)
        return (
            arguments_dict,
            serialize_json_compact_stable(arguments_dict),
            None,
        )
    if isinstance(raw_arguments, str):
        if not raw_arguments.strip():
            return (
                None,
                serialize_json_compact_stable({"raw": raw_arguments}),
                "Tool arguments must be valid JSON.",
            )
        try:
            parsed: JSONValue = parse_json_value(raw_arguments)
        except ValidationError:
            return (
                None,
                serialize_json_compact_stable({"raw": raw_arguments}),
                "Tool arguments must be valid JSON.",
            )
        if isinstance(parsed, dict):
            parsed_dict: JSONDict = dict(parsed)
            return (
                parsed_dict,
                serialize_json_compact_stable(parsed_dict),
                None,
            )
        return (
            None,
            serialize_json_compact_stable({"raw": raw_arguments}),
            "Tool arguments must be a JSON object.",
        )
    return (
        None,
        serialize_json_compact_stable({"raw": raw_arguments}),
        "Tool arguments must be a JSON object.",
    )
