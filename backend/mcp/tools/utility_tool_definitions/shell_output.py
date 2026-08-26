"""SoAI - MCP shell output tool definitions [backend/mcp/tools/utility_tool_definitions/shell_output.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_TERMINAL
from mcp.tools.shell_output_arguments import (
    DEFAULT_SHELL_OUTPUT_PAGE_LINES,
    MAX_SHELL_OUTPUT_PAGE_LINES,
)
from mcp.tools.utility_tool_definitions.terminal_session_schema import (
    build_terminal_session_output_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_shell_output_schema", "build_shell_output_tool_definitions")


def build_shell_output_schema() -> JSONDict:
    properties = build_terminal_session_output_properties()
    properties.update(
        {
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
            "returned_lines": {"type": "integer"},
            "total_lines": {"type": "integer"},
            "next_offset": {"type": ["integer", "null"]},
            "has_more": {"type": "boolean"},
            "output_offset_bytes": {"type": "integer"},
            "next_output_offset_bytes": {"type": "integer"},
            "transcript_truncated": {"type": "boolean"},
        },
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }


def build_shell_output_tool_definitions() -> dict[str, JSONDict]:
    return {
        "shell_output_read": {
            "title": "Read Shell Output",
            "description": (
                "Read a paginated shell transcript by line offset. Use this when shell or "
                "shell_write_stdin reports has_more=true or when inspecting earlier/later output."
            ),
            "icons": [build_tool_icon_entry(ICON_TERMINAL)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "session_id": {"type": "integer"},
                    "offset": {"type": "integer", "default": 1},
                    "limit": {
                        "type": "integer",
                        "default": DEFAULT_SHELL_OUTPUT_PAGE_LINES,
                        "description": f"Maximum lines to return (max {MAX_SHELL_OUTPUT_PAGE_LINES}).",
                    },
                    "from_end": {"type": "boolean", "default": False},
                },
                "required": ["session_id"],
            },
            "output_schema": build_shell_output_schema(),
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
        "shell_output_search": {
            "title": "Search Shell Output",
            "description": "Search a retained shell transcript and return matching line numbers/content.",
            "icons": [build_tool_icon_entry(ICON_TERMINAL)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "session_id": {"type": "integer"},
                    "query": {"type": "string"},
                    "offset": {"type": "integer", "default": 1},
                    "limit": {
                        "type": "integer",
                        "default": DEFAULT_SHELL_OUTPUT_PAGE_LINES,
                        "description": f"Maximum matches to return (max {MAX_SHELL_OUTPUT_PAGE_LINES}).",
                    },
                    "case_sensitive": {"type": "boolean", "default": False},
                },
                "required": ["session_id", "query"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "session_id": {"type": "integer"},
                    "query": {"type": "string"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"},
                    "total_lines": {"type": "integer"},
                    "returned_matches": {"type": "integer"},
                    "next_offset": {"type": ["integer", "null"]},
                    "has_more": {"type": "boolean"},
                    "transcript_truncated": {"type": "boolean"},
                    "matches": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "line": {"type": "integer"},
                                "content": {"type": "string"},
                            },
                        },
                    },
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
    }
