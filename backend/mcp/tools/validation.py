"""SoAI - MCP utility tools validation [backend/mcp/tools/validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.utility_definitions import build_internal_utility_tool_definitions

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.service import MCPUtilityTools

__all__ = ("validate_tool_definitions",)


def _coerce_input_schema(definition: JSONDict) -> JSONDict | None:
    input_schema = definition.get("input_schema")
    if not isinstance(input_schema, dict):
        return None
    return input_schema


def validate_tool_definitions(tool_handler: MCPUtilityTools) -> list[str]:
    errors: list[str] = []
    handlers = tool_handler.get_tool_handlers()
    definitions = build_internal_utility_tool_definitions()
    for tool_name, definition in definitions.items():
        if tool_name not in handlers:
            errors.append(
                f"Tool '{tool_name}' has schema but missing registered handler: {tool_name}",
            )
            continue
        handler = handlers[tool_name]
        if not callable(handler):
            errors.append(f"Tool '{tool_name}' registered handler is not callable: {tool_name}")
        if _coerce_input_schema(definition) is None:
            errors.append(f"Tool '{tool_name}' is missing input_schema object: {tool_name}")
    for tool_name in handlers:
        if tool_name not in definitions:
            errors.append(
                f"Tool '{tool_name}' has handler but missing schema definition: {tool_name}",
            )
    return errors
