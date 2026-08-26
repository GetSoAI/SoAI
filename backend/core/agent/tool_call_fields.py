"""SoAI - Agent tool-call field readers [backend/core/agent/tool_call_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from core.validation.strings import coerce_trimmed_str_or_empty

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "has_non_negative_tool_call_int",
    "resolve_tool_call_name",
)


def resolve_tool_call_name(tool_call: JSONDict) -> str:
    name = coerce_trimmed_str_or_empty(tool_call.get("name"))
    if name:
        return name
    function_value = tool_call.get("function")
    if not isinstance(function_value, dict):
        return ""
    return coerce_trimmed_str_or_empty(function_value.get("name"))


def has_non_negative_tool_call_int(value: JSONValue | None) -> bool:
    return coerce_optional_non_negative_int_strict(value) is not None
