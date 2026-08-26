"""SoAI - MCP utility tool definitions: browser_pdf [backend/mcp/tools/utility_tool_definitions/browser_pdf.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_PDF
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_boolean_schema,
    nullable_non_empty_string_schema,
    nullable_number_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_pdf_tool_definitions",)


def build_browser_pdf_tool_definitions() -> dict[str, JSONDict]:
    icons = [build_tool_icon_entry(ICON_BROWSER_PDF)]
    session_params = build_browser_session_param_properties()
    return {
        "browser_pdf": {
            "title": "Browser PDF",
            "description": (
                "Generate a PDF of the current page in Chromium-based sessions and return it as "
                "base64 with metadata."
            ),
            "icons": icons,
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "landscape": nullable_boolean_schema(),
                    "print_background": nullable_boolean_schema(),
                    "scale": nullable_number_schema(minimum=0.1, maximum=2.0),
                    "page_ranges": nullable_non_empty_string_schema(),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "content_type": {"type": "string"},
                    "bytes": {"type": "integer"},
                    "sha256": {"type": "string"},
                    "pdf_base64": {"type": "string"},
                    "pdf_error": {"type": "string"},
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True, open_world=True),
        },
    }
