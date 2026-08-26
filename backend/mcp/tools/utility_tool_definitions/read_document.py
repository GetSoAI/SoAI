"""SoAI - MCP utility tool definition: read_document [backend/mcp/tools/utility_tool_definitions/read_document.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_DOCUMENT
from mcp.tools.utility_tool_definitions.document_pipeline_output_schema import (
    build_document_pipeline_output_schema,
)
from mcp.tools.utility_tool_definitions.file_source_schema import (
    build_file_source_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_read_document_tool_definitions",)


def build_read_document_tool_definitions() -> dict[str, JSONDict]:
    return {
        "read_document": {
            "title": "Read Document (text + OCR)",
            "description": "Extract text from a document for LLM reading. Supports large documents via chunked reads: set max_chars and offset_chars; if truncated=true, continue with next_offset_chars. Uses the OCR-capable document pipeline for unreadable PDFs, scans, and images when OCR dependencies are available. Provide exactly one of file_id (uploaded file), document_id (RAG document), file_path (workspace_path path), or url (http/https). The file_path field also accepts an http/https URL.",
            "icons": [build_tool_icon_entry(ICON_DOCUMENT)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **build_file_source_properties(
                        file_path_description="Path to a document under workspace_path (or an absolute path within it).",
                        include_url=True,
                        url_description="http/https URL to download and read (saved to a temporary file during parsing, deleted afterward).",
                    ),
                    "max_chars": {
                        "type": "integer",
                        "default": 20000,
                        "description": "Maximum characters to return for this call. Use offset_chars/next_offset_chars to read the full document in chunks.",
                    },
                    "offset_chars": {
                        "type": "integer",
                        "default": 0,
                        "description": "Character offset into the extracted text to start reading from.",
                    },
                    "parse_timeout_sec": {
                        "type": "integer",
                        "default": 30,
                        "description": "Timeout in seconds for parsing/OCR work (increase for large PDFs or OCR-heavy scans).",
                    },
                },
                "required": [],
            },
            "output_schema": build_document_pipeline_output_schema(),
            "annotations": build_tool_annotation_flags(
                read_only=True,
                idempotent=True,
                open_world=True,
            ),
        },
    }
