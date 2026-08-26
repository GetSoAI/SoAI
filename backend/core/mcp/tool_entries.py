"""SoAI - Shared MCP tool entry payload shaping [backend/core/mcp/tool_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SOAI_MCP_SERVER_ID",
    "SOAI_MCP_SERVER_NAME",
    "build_remote_tool_entry",
    "build_tool_entry",
)

SOAI_MCP_SERVER_ID: str = "builtin"
SOAI_MCP_SERVER_NAME: str = "SoAI"


def build_tool_entry(
    *,
    name: str,
    definition: Mapping[str, JSONValue],
) -> JSONDict:
    return {
        key: value
        for key, value in {
            "name": name,
            "description": definition.get("description", f"SoAI tool: {name}"),
            "inputSchema": definition.get("input_schema", {"type": "object", "properties": {}}),
            "title": definition.get("title"),
            "outputSchema": definition.get("output_schema"),
            "annotations": definition.get("annotations"),
            "icons": definition.get("icons"),
        }.items()
        if value is not None
    }


def build_remote_tool_entry(
    *,
    name: str,
    tool_definition: Mapping[str, JSONValue],
) -> JSONDict:
    return {
        key: value
        for key, value in {
            "name": name,
            "description": tool_definition.get("description"),
            "inputSchema": tool_definition.get("inputSchema", {"type": "object", "properties": {}}),
            "title": tool_definition.get("title"),
            "outputSchema": tool_definition.get("outputSchema"),
            "annotations": tool_definition.get("annotations"),
            "icons": tool_definition.get("icons"),
        }.items()
        if value is not None
    }
