"""SoAI - MCP utility tool definition: list_dir [backend/mcp/tools/utility_tool_definitions/list_dir.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_FOLDER

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_list_dir_tool_definitions",)


def build_list_dir_tool_definitions() -> dict[str, JSONDict]:
    return {
        "list_dir": {
            "title": "List Dir",
            "description": "List files and directories under workspace_path.",
            "icons": [build_tool_icon_entry(ICON_FOLDER)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path under workspace_path (or an absolute path within it). Empty or omitted means workspace_path.",
                    },
                    "offset": {
                        "type": "integer",
                        "default": 1,
                        "description": "1-based index to start listing from (default 1). Use next_offset from a previous response to paginate.",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 25,
                        "description": "Maximum number of entries to return per page (default 25, max 2000).",
                    },
                    "depth": {
                        "type": "integer",
                        "default": 2,
                        "description": "Maximum directory depth to recurse (default 2, max 20). 1 means only the immediate directory.",
                    },
                },
                "required": [],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"},
                    "depth": {"type": "integer"},
                    "total_entries": {"type": ["integer", "null"]},
                    "truncated": {"type": "boolean"},
                    "has_more": {"type": "boolean"},
                    "next_offset": {"type": ["integer", "null"]},
                    "entries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "Absolute path to the entry.",
                                },
                                "type": {
                                    "type": "string",
                                    "enum": ["file", "directory"],
                                    "description": "Whether this entry is a file or directory.",
                                },
                            },
                        },
                    },
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        },
    }
