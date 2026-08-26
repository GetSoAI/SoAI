"""SoAI - MCP utility tool definition: replace_in_file [backend/mcp/tools/utility_tool_definitions/replace_in_file.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_REPLACE
from mcp.tools.utility_tool_definitions.code_diffs_schema import build_code_diffs_schema

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_replace_in_file_tool_definitions",)


def build_replace_in_file_tool_definitions() -> dict[str, JSONDict]:
    return {
        "replace_in_file": {
            "title": "Replace In File",
            "description": (
                "Replace occurrences of a literal string in a file. "
                "Case-sensitive, not regex. "
                "By default, the operation is fail-safe: it requires exactly one match unless you explicitly set "
                "replace_all or expected_replacements. "
                "When the read-before-write file guard is enabled, edits to existing files require "
                "a prior read_file of the target file in line-based mode. "
                "This tool operates on utf-8 text files only."
            ),
            "icons": [build_tool_icon_entry(ICON_REPLACE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file under workspace_path (or an absolute path within it).",
                    },
                    "find": {
                        "type": "string",
                        "description": "Exact string to find (literal match, case-sensitive).",
                    },
                    "replace": {"type": "string", "description": "Replacement string."},
                    "replace_all": {
                        "type": "boolean",
                        "description": "If true, allow replacing all occurrences when multiple matches are found (otherwise multiple matches are rejected).",
                    },
                    "allow_noop": {
                        "type": "boolean",
                        "description": "If true, allow a no-op when no matches are found (otherwise zero matches is an error).",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, compute replacements and return a unified diff but do not write to disk.",
                    },
                    "expected_replacements": {
                        "type": "integer",
                        "description": (
                            "Expected number of matches/replacements. "
                            "If provided and the actual count differs, the operation fails with an error. "
                            "If set to 0, zero matches are allowed without allow_noop."
                        ),
                    },
                },
                "required": ["file_path", "find", "replace"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "replacements": {"type": "integer"},
                    "changed": {"type": "boolean"},
                    "committed": {"type": "boolean"},
                    "dry_run": {"type": "boolean"},
                    "code_diffs": build_code_diffs_schema(),
                },
            },
            "annotations": build_tool_annotation_flags(destructive=True),
        },
    }
