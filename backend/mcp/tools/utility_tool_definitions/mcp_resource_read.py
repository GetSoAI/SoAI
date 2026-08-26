"""SoAI - MCP utility tool definition: mcp_resource_read [backend/mcp/tools/utility_tool_definitions/mcp_resource_read.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_RESOURCE

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_mcp_resource_read_tool_definitions",)


def build_mcp_resource_read_tool_definitions() -> dict[str, JSONDict]:
    return {
        "mcp_resource_read": {
            "title": "Read MCP Resource",
            "description": "Read a resource from a connected MCP server.",
            "icons": [build_tool_icon_entry(ICON_RESOURCE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "server": {
                        "type": "string",
                        "description": "Server ID of the MCP server that hosts the resource.",
                    },
                    "uri": {
                        "type": "string",
                        "description": "Resource URI to read (as listed by mcp_resources_list).",
                    },
                },
                "required": ["server", "uri"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "contents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "uri": {"type": "string", "description": "Resource URI."},
                                "text": {"type": "string", "description": "Resource text content."},
                                "mimeType": {"type": "string", "description": "Content MIME type."},
                            },
                        },
                    },
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
    }
