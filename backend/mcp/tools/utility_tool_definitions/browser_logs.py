"""SoAI - MCP utility tool definitions: browser logs [backend/mcp/tools/utility_tool_definitions/browser_logs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_CONSOLE, ICON_BROWSER_NETWORK
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_boolean_schema,
    nullable_enum_schema,
    nullable_integer_schema,
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_logs_tool_definitions",)


def build_browser_logs_tool_definitions() -> dict[str, JSONDict]:
    session_params = build_browser_session_param_properties()
    since_schema = nullable_enum_schema(("last_call", "page_load"))
    return {
        "browser_console": {
            "title": "Browser Console Messages",
            "description": (
                "Return console messages captured from the browser session for debugging page "
                "behavior."
            ),
            "icons": [build_tool_icon_entry(ICON_BROWSER_CONSOLE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "since": since_schema,
                    "type_filter": nullable_enum_schema(
                        ("all", "errors", "warnings", "errors_warnings"),
                    ),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "text": {"type": "string"},
                                "url": {"type": "string"},
                                "line": {"type": "integer"},
                                "column": {"type": "integer"},
                                "count": {"type": "integer"},
                            },
                        },
                    },
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True),
        },
        "browser_network": {
            "title": "Browser Network Requests",
            "description": (
                "Return captured network request and response metadata from the browser session "
                "for debugging page behavior. Use cursor + max_requests to page through large "
                "captures without advancing the session's last_call cursor."
            ),
            "icons": [build_tool_icon_entry(ICON_BROWSER_NETWORK)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "since": since_schema,
                    "cursor": {
                        **nullable_integer_schema(minimum=0, maximum=10_000_000),
                        "description": (
                            "Absolute cursor into the captured request list. Mutually exclusive "
                            "with since. When provided, the tool does not advance the session's "
                            "last_call cursor."
                        ),
                    },
                    "resource_type": nullable_non_empty_string_schema(),
                    "status_gte": nullable_integer_schema(minimum=0, maximum=999),
                    "include_body": nullable_boolean_schema(),
                    "max_requests": nullable_integer_schema(
                        minimum=1,
                        maximum=500,
                        description="Maximum number of requests to return (default 200).",
                    ),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "requests": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "method": {"type": "string"},
                                "status": {"type": "integer"},
                                "resource_type": {"type": "string"},
                                "body": {"type": "string"},
                                "body_truncated": {"type": "boolean"},
                            },
                        },
                    },
                    "has_more": {"type": "boolean"},
                    "cursor_start": {"type": "integer"},
                    "cursor_next": {"type": "integer"},
                    "total_captured": {"type": "integer"},
                    "returned": {"type": "integer"},
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True),
        },
    }
