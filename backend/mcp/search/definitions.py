"""SoAI - MCP search tool definitions [backend/mcp/search/definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mcp.schema import (
    build_search_results_schema,
    build_title_property_schema,
    build_tool_annotation_flags,
    build_tool_icon_entry,
)
from core.types.json import JSONDict, JSONValue
from mcp.protocol.icons import ICON_SEARCH
from mcp.search.providers import get_search_provider_specs

__all__ = ("build_mcp_search_tool_definitions",)


def build_mcp_search_tool_definitions() -> dict[str, JSONDict]:
    search_result_item_properties: JSONDict = {
        **build_title_property_schema(),
        "snippet": {"type": "string"},
        "url": {"type": "string"},
        "source": {"type": "string"},
    }
    output_schema = build_search_results_schema(search_result_item_properties)
    definitions: dict[str, JSONDict] = {}
    provider_icons = [build_tool_icon_entry(ICON_SEARCH)]
    shared_annotations = build_tool_annotation_flags(
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=True,
    )
    shared_properties: dict[str, dict[str, JSONValue]] = {
        "query": {"type": "string", "description": "Search query"},
        "limit": {
            "type": "integer",
            "description": "Maximum number of results (default 5, max 25)",
            "default": 5,
            "minimum": 1,
            "maximum": 25,
        },
    }
    for provider in get_search_provider_specs():
        provider_input_properties = dict[str, JSONValue](provider.input_properties)
        definitions[f"web_search_{provider.provider_name}"] = {
            "title": provider.tool_title,
            "icons": provider_icons,
            "description": provider.tool_description,
            "input_schema": {
                "type": "object",
                "properties": {
                    **shared_properties,
                    **provider_input_properties,
                },
                "required": ["query"],
            },
            "output_schema": output_schema,
            "annotations": shared_annotations,
        }
    return definitions
