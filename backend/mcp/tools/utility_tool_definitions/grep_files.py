"""SoAI - MCP utility tool definition: grep_files [backend/mcp/tools/utility_tool_definitions/grep_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.grep_types import (
    DEFAULT_PER_FILE_COUNT,
    DEFAULT_SEARCH_LIMIT,
    MAX_CONTEXT_LINES,
    MAX_PER_FILE_COUNT,
    MAX_SEARCH_LIMIT,
)
from mcp.tools.icons import ICON_SEARCH
from mcp.tools.utility_tool_definitions.file_search_schema import (
    build_file_search_input_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_grep_files_tool_definitions",)


def build_grep_files_tool_definitions() -> dict[str, JSONDict]:
    return {
        "grep_files": {
            "title": "Search Files",
            "description": (
                "Search files under workspace_path with a regex pattern. "
                "Returns matching file paths, per-file match counts, or matching "
                "lines with line numbers and optional context, depending on "
                "output_mode. Backed by a managed ripgrep binary."
            ),
            "icons": [build_tool_icon_entry(ICON_SEARCH)],
            "input_schema": build_file_search_input_schema(
                pattern_description="Regex pattern to search for.",
                properties={
                    "include": {
                        "type": "string",
                        "description": "Glob pattern to filter which files are searched (matched against filename and relative path).",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory under workspace_path (or an absolute path within it) to scope the search. Defaults to workspace_path.",
                    },
                    "output_mode": {
                        "type": "string",
                        "enum": ["content", "files_with_matches", "count"],
                        "default": "files_with_matches",
                        "description": "How to shape the result. 'files_with_matches' returns file paths only; 'count' returns per-file match totals; 'content' returns matching lines with line numbers and optional context.",
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "default": False,
                        "description": "Match the pattern case-insensitively.",
                    },
                    "multiline": {
                        "type": "boolean",
                        "description": "Allow the pattern to span multiple lines (rg -U --multiline-dotall). Defaults to false; content mode only.",
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Restrict the search to a ripgrep file type (e.g. 'py', 'ts', 'rs').",
                    },
                    "before_context": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_CONTEXT_LINES,
                        "description": "Number of lines of context to include before each match (defaults to 0; content mode only).",
                    },
                    "after_context": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_CONTEXT_LINES,
                        "description": "Number of lines of context to include after each match (defaults to 0; content mode only).",
                    },
                    "context": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_CONTEXT_LINES,
                        "description": "Shorthand for setting before_context and after_context to the same value (defaults to 0; content mode only).",
                    },
                    "head_limit": {
                        "type": "integer",
                        "default": DEFAULT_SEARCH_LIMIT,
                        "minimum": 1,
                        "maximum": MAX_SEARCH_LIMIT,
                        "description": f"Maximum number of matching files to return (default {DEFAULT_SEARCH_LIMIT}, max {MAX_SEARCH_LIMIT}).",
                    },
                    "offset": {
                        "type": "integer",
                        "default": 0,
                        "minimum": 0,
                        "description": "Number of leading matching files to skip before returning results (for pagination).",
                    },
                    "max_count_per_file": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_PER_FILE_COUNT,
                        "description": f"Cap on matches returned per file in content mode (default {DEFAULT_PER_FILE_COUNT}, max {MAX_PER_FILE_COUNT}).",
                    },
                },
            ),
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "pattern": {"type": "string"},
                    "include": {"type": "string"},
                    "path": {"type": "string"},
                    "output_mode": {
                        "type": "string",
                        "enum": ["content", "files_with_matches", "count"],
                    },
                    "head_limit": {"type": "integer"},
                    "offset": {"type": "integer"},
                    "truncated": {"type": "boolean"},
                    "truncated_reason": {
                        "type": "string",
                        "enum": ["head_limit"],
                    },
                    "total_matches": {"type": "integer"},
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "path": {"type": "string"},
                                "match_count": {"type": "integer"},
                                "lines": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "line_number": {"type": "integer"},
                                            "text": {"type": "string"},
                                            "is_context": {"type": "boolean"},
                                        },
                                    },
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
