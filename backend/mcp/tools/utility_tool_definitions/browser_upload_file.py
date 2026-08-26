"""SoAI - MCP utility tool definitions: browser_upload_file [backend/mcp/tools/utility_tool_definitions/browser_upload_file.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_UPLOAD
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    non_empty_string_array_schema,
    non_empty_string_schema,
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_upload_file_tool_definitions",)


def build_browser_upload_file_tool_definitions() -> dict[str, JSONDict]:
    icons = [build_tool_icon_entry(ICON_BROWSER_UPLOAD)]
    session_params = build_browser_session_param_properties()
    return {
        "browser_upload_file": {
            "title": "Browser Upload File",
            "description": "Upload one or more files under workspace_path to a file input element by ref.",
            "icons": icons,
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ref", "filenames"],
                "properties": {
                    "element": nullable_non_empty_string_schema(
                        description="Optional human-readable element description.",
                    ),
                    "ref": non_empty_string_schema(
                        description="Element ref from browser_snapshot.",
                    ),
                    "filenames": non_empty_string_array_schema(
                        description="File paths relative to workspace_path, or absolute paths that still resolve within workspace_path.",
                        max_items=20,
                    ),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "uploaded": {"type": "boolean"},
                    "files": {"type": "array", "items": {"type": "string"}},
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=False,
                destructive=False,
                idempotent=False,
                open_world=True,
            ),
        },
    }
