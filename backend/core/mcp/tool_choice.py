"""SoAI - Core MCP tool choice utilities [backend/core/mcp/tool_choice.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, NoReturn, override

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "ToolChoiceError",
    "extract_tool_names",
    "normalize_tool_choice",
)


class ToolChoiceError(ValidationError):
    def __init__(self, message: str, *, is_invalid_request: bool = True) -> None:
        super().__init__(message)
        self.is_invalid_request = is_invalid_request

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return ((self.message,), {"is_invalid_request": self.is_invalid_request})


def normalize_tool_choice(
    tool_choice: JSONValue,
) -> tuple[str | None, str | None]:
    if tool_choice is None:
        return (None, None)
    if isinstance(tool_choice, dict):
        tool_type = tool_choice.get("type", "function")
        if tool_type != "function":
            raise ToolChoiceError("tool_choice type must be 'function'.", is_invalid_request=True)
        function = tool_choice.get("function")
        if not isinstance(function, dict):
            raise ToolChoiceError(
                "tool_choice.function must be an object.",
                is_invalid_request=True,
            )
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ToolChoiceError(
                "tool_choice.function.name must be a non-empty string.",
                is_invalid_request=True,
            )
        return ("function", name.strip())
    if isinstance(tool_choice, str):
        normalized = tool_choice.strip()
        if not normalized:
            return (None, None)
        lowered = normalized.lower()
        if lowered in {"auto", "none", "required"}:
            return (lowered, None)
        return ("function", normalized)
    raise ToolChoiceError("tool_choice must be a string or object.", is_invalid_request=False)


def extract_tool_names(
    tools_payload: JSONValue,
    on_error: Callable[[str], NoReturn] | None = None,
) -> list[str]:
    if tools_payload is None:
        return []
    if not isinstance(tools_payload, list):
        if on_error:
            on_error("tools must be an array.")
        return []
    names: list[str] = []
    for tool in tools_payload:
        if not isinstance(tool, dict):
            if on_error:
                on_error("Each tool must be an object.")
            continue
        tool_type = tool.get("type", "function")
        if tool_type != "function":
            if on_error:
                on_error("Only function tools are supported.")
            continue
        function = tool.get("function")
        if not isinstance(function, dict):
            if on_error:
                on_error("Tool function must be an object.")
            continue
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            if on_error:
                on_error("Tool function name must be a non-empty string.")
            continue
        names.append(name.strip())
    return list(dict.fromkeys(names))
