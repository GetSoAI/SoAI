"""SoAI - MCP resource list schema primitives [backend/mcp/tools/utility_tool_definitions/mcp_resource_list_schemas.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_mcp_resource_list_input_schema",
    "build_mcp_resource_list_output_schema",
)


def build_mcp_resource_list_input_schema(*, server_description: str) -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "server": {
                "type": "string",
                "description": server_description,
            },
            "cursor": {
                "type": "string",
                "description": "Pagination cursor from a previous response's nextCursor field. Only valid when server is provided.",
            },
        },
        "required": [],
    }


def build_mcp_resource_list_output_schema(*, list_field_name: str) -> JSONDict:
    return {
        "type": "object",
        "properties": {
            list_field_name: {"type": "array", "items": {"type": "object"}},
            "nextCursor": {"type": "string"},
        },
    }
