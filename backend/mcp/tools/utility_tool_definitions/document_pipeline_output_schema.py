"""SoAI - MCP shared output schema for the document text extraction pipeline [backend/mcp/tools/utility_tool_definitions/document_pipeline_output_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_document_pipeline_output_schema",)


def build_document_pipeline_output_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "content": {"type": "string"},
            "parser_used": {"type": "string"},
            "detected_type": {"type": "string"},
            "page_count": {"type": ["integer", "null"]},
            "metadata": {"type": "object"},
            "truncated": {"type": "boolean"},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "offset_chars": {"type": "integer"},
            "next_offset_chars": {"type": ["integer", "null"]},
            "total_chars": {"type": ["integer", "null"]},
            "extraction_state": {
                "type": "string",
                "enum": ["complete", "degraded", "unsupported", "failed", "timed_out"],
            },
        },
    }
