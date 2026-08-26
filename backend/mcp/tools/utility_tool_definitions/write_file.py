"""SoAI - MCP utility tool definition: write_file [backend/mcp/tools/utility_tool_definitions/write_file.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_FILE_WRITE
from mcp.tools.utility_tool_definitions.code_diffs_schema import build_code_diffs_schema
from mcp.tools.utility_tool_definitions.workspace_path_schema import (
    build_workspace_file_path_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_write_file_tool_definitions",)


def build_write_file_tool_definitions() -> dict[str, JSONDict]:
    return {
        "write_file": {
            "title": "Write File",
            "description": (
                "Create or overwrite a UTF-8 text file under workspace_path. "
                "Overwriting requires overwrite=true. When the read-before-write file guard is enabled, "
                "overwriting an existing file requires a prior read_file of the target file in line-based "
                "mode; "
                "the server rejects overwrites when the file changed since it was last read. "
                "code_diffs contains unified diffs; it is truncated when over the response budget and empty when content is unchanged. "
                "Set dry_run=true to validate and preview diffs without writing to disk."
            ),
            "icons": [build_tool_icon_entry(ICON_FILE_WRITE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "file_path": build_workspace_file_path_schema(
                        description="Path under workspace_path (or an absolute path within it).",
                    ),
                    "content": {"type": "string"},
                    "overwrite": {
                        "type": "boolean",
                        "default": False,
                        "description": "Set to true to overwrite an existing file. If false (default) and the file already exists, the operation fails with an error.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, do not write to disk. Validates inputs and returns code_diffs for what would change.",
                    },
                },
                "required": ["file_path", "content"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "bytes": {"type": "integer"},
                    "existed_before": {"type": "boolean"},
                    "changed": {"type": "boolean"},
                    "committed": {"type": "boolean"},
                    "dry_run": {"type": "boolean"},
                    "code_diffs": build_code_diffs_schema(),
                },
                "required": [
                    "path",
                    "bytes",
                    "existed_before",
                    "changed",
                    "committed",
                    "dry_run",
                    "code_diffs",
                ],
            },
            "annotations": build_tool_annotation_flags(destructive=True),
        },
    }
