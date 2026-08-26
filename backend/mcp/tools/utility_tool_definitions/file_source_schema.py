"""SoAI - MCP utility tool shared file source schema helpers [backend/mcp/tools/utility_tool_definitions/file_source_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_file_source_properties",)


def build_file_source_properties(
    *,
    file_path_description: str,
    include_url: bool,
    url_description: str,
) -> dict[str, JSONDict]:
    properties: dict[str, JSONDict] = {
        "file_id": {
            "type": "string",
            "description": "ID of an uploaded file from /v1/files endpoint (e.g., 'file-abc123')",
        },
        "document_id": {
            "type": "string",
            "description": "ID of a RAG document",
        },
        "file_path": {
            "type": "string",
            "description": str(file_path_description or "").strip() or "Path to a local file.",
        },
    }
    if include_url:
        properties["url"] = {
            "type": "string",
            "description": str(url_description or "").strip() or "http/https URL.",
        }
    return properties
