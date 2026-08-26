"""SoAI - Shared agent request payload assembly [backend/features/agent/runtime/request_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict

__all__ = ("collect_tool_definitions",)


def collect_tool_definitions(tool_context: MCPToolContext | None) -> list[JSONDict]:
    if tool_context is None:
        return []
    tool_definitions: list[JSONDict] = []
    for tool_name, tool_entry in tool_context.tool_map.items():
        definition = tool_entry.get("definition")
        if not isinstance(definition, dict):
            raise ValidationError(f"MCP tool '{tool_name}' definition is invalid.")
        tool_definitions.append(definition)
    return tool_definitions
