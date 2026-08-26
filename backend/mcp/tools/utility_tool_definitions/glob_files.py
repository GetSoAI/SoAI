"""SoAI - MCP utility tool definition: glob_files [backend/mcp/tools/utility_tool_definitions/glob_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_SEARCH
from mcp.tools.utility_tool_definitions.file_search_schema import (
    build_file_search_input_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_glob_files_tool_definitions",)


def build_glob_files_tool_definitions() -> dict[str, JSONDict]:
    return {
        "glob_files": {
            "title": "Glob Files",
            "description": "Find files by glob pattern under workspace_path.",
            "icons": [build_tool_icon_entry(ICON_SEARCH)],
            "input_schema": build_file_search_input_schema(
                pattern_description="Glob pattern to match paths (files and directories). Supports fnmatch syntax plus brace expansion (e.g. '**/{backend,frontend,soai.sh}', '*.py', 'src/**/*.ts'). Patterns are matched against paths relative to the search root and against the basename.",
                properties={
                    "path": {
                        "type": "string",
                        "description": "Directory to search in, under workspace_path (or an absolute path within it). Defaults to workspace_path.",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 250,
                        "description": "Maximum number of matches to return (default 250, max 5000).",
                    },
                    "sort": {
                        "type": "string",
                        "default": "modified_desc",
                        "enum": ["modified_desc", "modified_asc", "name_asc", "name_desc"],
                        "description": "Sort order for matches (default modified_desc).",
                    },
                },
            ),
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                    "limit": {"type": "integer"},
                    "sort": {
                        "type": "string",
                        "enum": ["modified_desc", "modified_asc", "name_asc", "name_desc"],
                    },
                    "total_matches": {"type": "integer"},
                    "truncated": {"type": "boolean"},
                    "matches": {"type": "array", "items": {"type": "string"}},
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
