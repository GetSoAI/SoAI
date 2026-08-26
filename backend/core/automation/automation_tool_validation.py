"""SoAI - Automation MCP tool-name validation helpers [backend/core/automation/automation_tool_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Iterable

from core.errors.exceptions import ValidationError
from core.mcp.qualified_name import decode_qualified_tool_name
from core.types.json import JSONValue

__all__ = (
    "build_automation_tool_name_validator",
    "filter_disallowed_automation_tool_names",
    "is_disallowed_automation_tool_name",
    "normalize_automation_disallowed_unqualified_tools",
)


def normalize_automation_disallowed_unqualified_tools(
    value: JSONValue,
    *,
    field_label: str,
) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValidationError(f"{field_label} must be an array.")
    normalized: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise ValidationError(f"{field_label} entries must be strings.")
        candidate = entry.strip()
        if not candidate:
            raise ValidationError(f"{field_label} entries cannot be empty.")
        if candidate not in normalized:
            normalized.append(candidate)
    return tuple(normalized)


def is_disallowed_automation_tool_name(
    tool_name: str,
    *,
    disallowed_unqualified_tools: tuple[str, ...],
) -> bool:
    _, decoded_name = decode_qualified_tool_name(tool_name)
    return decoded_name in disallowed_unqualified_tools


def build_automation_tool_name_validator(
    disallowed_unqualified_tools: tuple[str, ...],
) -> Callable[[str], None]:
    def _reject(tool_name: str) -> None:
        if is_disallowed_automation_tool_name(
            tool_name,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        ):
            raise ValidationError(f"Automation MCP tool '{tool_name}' is not allowed.")

    return _reject


def filter_disallowed_automation_tool_names(
    tool_names: Iterable[str],
    *,
    disallowed_unqualified_tools: tuple[str, ...],
) -> list[str]:
    filtered: list[str] = []
    for tool_name in tool_names:
        if is_disallowed_automation_tool_name(
            tool_name,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        ):
            continue
        if tool_name not in filtered:
            filtered.append(tool_name)
    return filtered
