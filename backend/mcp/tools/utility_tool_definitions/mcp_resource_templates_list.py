"""SoAI - MCP utility tool definition: mcp_resource_templates_list [backend/mcp/tools/utility_tool_definitions/mcp_resource_templates_list.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_RESOURCE
from mcp.tools.utility_tool_definitions.mcp_resource_list_schemas import (
    build_mcp_resource_list_input_schema,
    build_mcp_resource_list_output_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_mcp_resource_templates_list_tool_definitions",)


def build_mcp_resource_templates_list_tool_definitions() -> dict[str, JSONDict]:
    return {
        "mcp_resource_templates_list": {
            "title": "List MCP Resource Templates",
            "description": "List resource templates from connected MCP servers.",
            "icons": [build_tool_icon_entry(ICON_RESOURCE)],
            "input_schema": build_mcp_resource_list_input_schema(
                server_description="Server ID to list templates from. Omit to list templates from all connected MCP servers.",
            ),
            "output_schema": build_mcp_resource_list_output_schema(
                list_field_name="resourceTemplates",
            ),
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        },
    }
