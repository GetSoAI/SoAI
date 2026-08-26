"""SoAI - MCP utility tool definition: read_image [backend/mcp/tools/utility_tool_definitions/read_image.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_IMAGE
from mcp.tools.utility_tool_definitions.workspace_path_schema import (
    build_workspace_file_path_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_read_image_tool_definitions",)


def build_read_image_tool_definitions() -> dict[str, JSONDict]:
    return {
        "read_image": {
            "title": "Read Image",
            "description": (
                "Read an image under workspace_path for vision-native inspection. "
                "Use read_document only when OCR/text extraction is needed."
            ),
            "icons": [build_tool_icon_entry(ICON_IMAGE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "file_path": build_workspace_file_path_schema(
                        description="Path to an image under workspace_path (or an absolute path within it).",
                    ),
                },
                "required": ["file_path"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "content_type": {"type": "string"},
                    "image_base64": {"type": "string"},
                    "size_bytes": {"type": "integer"},
                    "source_size_bytes": {"type": "integer"},
                    "source_mime_type": {"type": "string"},
                    "encoded_chars": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "source_width": {"type": "integer"},
                    "source_height": {"type": "integer"},
                },
                "required": [
                    "path",
                    "content_type",
                    "image_base64",
                    "size_bytes",
                    "source_size_bytes",
                    "source_mime_type",
                    "encoded_chars",
                    "width",
                    "height",
                    "source_width",
                    "source_height",
                ],
            },
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
    }
