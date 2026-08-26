"""SoAI - MCP utility tool definition: read_file [backend/mcp/tools/utility_tool_definitions/read_file.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_FILE
from mcp.tools.utility_tool_definitions.workspace_path_schema import (
    build_workspace_file_path_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_read_file_tool_definitions",)


def build_read_file_tool_definitions() -> dict[str, JSONDict]:
    line_based_output_schema: JSONDict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string"},
            "mode": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
            "total_lines": {"type": "integer"},
            "returned_lines": {"type": "integer"},
            "start_line": {"type": ["integer", "null"]},
            "end_line": {"type": ["integer", "null"]},
            "next_offset": {"type": ["integer", "null"]},
            "truncated": {"type": "boolean"},
            "truncation_reason": {"type": ["string", "null"]},
            "content_truncated": {"type": "boolean"},
            "serialized_response_chars": {"type": "integer"},
            "max_serialized_response_chars": {"type": ["integer", "null"]},
            "content": {"type": "string"},
            "binary": {"type": "boolean"},
            "rendered_as_text": {"type": "boolean"},
            "content_omitted": {"type": "boolean"},
            "content_omitted_reason": {"type": "string"},
            "mime_type": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "max_size_bytes": {"type": "integer"},
            "read_image_hint": {"type": "string"},
            "read_image_args": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "file_path": {"type": "string"},
                },
                "required": ["file_path"],
            },
            "indentation": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "anchor_line": {"type": "integer"},
                    "max_levels": {"type": "integer"},
                    "include_siblings": {"type": "boolean"},
                    "include_header": {"type": "boolean"},
                    "max_lines": {"type": "integer"},
                },
            },
        },
        "required": [
            "path",
            "mode",
            "offset",
            "limit",
            "total_lines",
            "returned_lines",
            "start_line",
            "end_line",
            "next_offset",
            "truncated",
            "truncation_reason",
            "content_truncated",
            "serialized_response_chars",
            "max_serialized_response_chars",
            "content",
        ],
    }
    return {
        "read_file": {
            "title": "Read File",
            "description": (
                "Read a UTF-8 text file under workspace_path using line slicing, indentation views, "
                "or raw full-file reads. This tool is for source, config, log, and other text files."
            ),
            "icons": [build_tool_icon_entry(ICON_FILE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "file_path": build_workspace_file_path_schema(
                        description="Path to a file under workspace_path (or an absolute path within it).",
                    ),
                    "offset": {
                        "type": ["integer", "null"],
                        "description": "1-based line to start from in 'slice'/'indentation' modes (defaults to line 1). Not accepted by mode='raw'.",
                    },
                    "limit": {
                        "type": ["integer", "null"],
                        "description": "Maximum number of lines to return in 'slice'/'indentation' modes (defaults to 2000). Not accepted by mode='raw'.",
                    },
                    "mode": {
                        "type": "string",
                        "default": "slice",
                        "description": "Read mode: 'slice' returns prompt-safe line chunks by offset/limit (default), 'indentation' returns prompt-safe context around an anchor line based on indentation structure, 'raw' reads the full file only and rejects offset/limit/render/indentation. Use mode='slice' with render='raw' for chunked unnumbered reads.",
                    },
                    "render": {
                        "type": ["string", "null"],
                        "description": "Render mode for 'slice'/'indentation': 'raw' returns unnumbered content suitable for patch generation (defaults to 'raw'); 'numbered' prefixes each line with '<n>: ' for display. Not accepted by mode='raw'.",
                    },
                    "indentation": {
                        "type": ["object", "null"],
                        "additionalProperties": False,
                        "properties": {
                            "anchor_line": {
                                "type": "integer",
                                "description": "Line number to center the indentation-based view on.",
                            },
                            "max_levels": {
                                "type": "integer",
                                "description": "Maximum indentation levels to include above and below the anchor.",
                            },
                            "include_siblings": {
                                "type": "boolean",
                                "description": "Include sibling blocks at the same indentation level as the anchor.",
                            },
                            "include_header": {
                                "type": "boolean",
                                "description": "Include the file-level header (e.g. imports, module docstring).",
                            },
                            "max_lines": {
                                "type": "integer",
                                "description": "Maximum total lines to return in indentation mode.",
                            },
                        },
                    },
                },
                "required": ["file_path"],
            },
            "output_schema": line_based_output_schema,
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
    }
