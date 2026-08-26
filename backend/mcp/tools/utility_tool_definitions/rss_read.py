"""SoAI - MCP utility tool definition: rss_read [backend/mcp/tools/utility_tool_definitions/rss_read.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import (
    build_title_property_schema,
    build_tool_annotation_flags,
    build_tool_icon_entry,
)
from mcp.tools.icons import ICON_RSS

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_rss_read_tool_definitions",)


def build_rss_read_tool_definitions() -> dict[str, JSONDict]:
    return {
        "rss_read": {
            "title": "RSS Feed Reader",
            "description": "Fetch and parse RSS or Atom feed from a URL, returning structured feed items",
            "icons": [build_tool_icon_entry(ICON_RSS)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the RSS/Atom feed",
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "Maximum number of items to return (default 10, max 100)",
                    },
                },
                "required": ["url"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "feed_title": {"type": "string"},
                    "feed_link": {"type": "string"},
                    "feed_description": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                **build_title_property_schema(),
                                "link": {"type": "string"},
                                "description": {"type": "string"},
                                "published": {"type": "string"},
                                "author": {"type": "string"},
                            },
                        },
                    },
                    "item_count": {"type": "integer"},
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=True,
            ),
        },
    }
