"""SoAI - MCP RAG tool schema helpers [backend/mcp/rag/tool_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_icon_entry

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_tool",
    "prop_chunk_overlap",
    "prop_chunk_size",
    "prop_conv_id",
    "prop_embedding_model",
)

ICON_REFRESH = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpolyline points='23 4 23 10 17 10'/%3E%3Cpolyline points='1 20 1 14 7 14'/%3E%3Cpath d='M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15'/%3E%3C/svg%3E"

CONV_ID_DESC = "SoAI conversation id (e.g., 'conv_<uuid>')."
CHUNK_SIZE_DESC = "Chunk size in tokens (default 500)"
CHUNK_OVERLAP_DESC = "Overlap between chunks in tokens (default 100)"
EMBEDDING_MODEL_DESC = "Embedding model to use (default: auto)"


def prop_conv_id() -> JSONDict:
    return {"type": "string", "description": CONV_ID_DESC}


def prop_chunk_size() -> JSONDict:
    return {"type": "integer", "description": CHUNK_SIZE_DESC}


def prop_chunk_overlap() -> JSONDict:
    return {"type": "integer", "description": CHUNK_OVERLAP_DESC}


def prop_embedding_model() -> JSONDict:
    return {"type": "string", "description": EMBEDDING_MODEL_DESC}


def build_tool(
    title: str,
    icon_src: str,
    description: str,
    input_properties: JSONDict,
    required: list[str],
    output_schema: JSONDict,
    annotations: dict[str, bool],
) -> JSONDict:
    return {
        "title": title,
        "icons": [build_tool_icon_entry(icon_src)],
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": input_properties,
            "required": required,
        },
        "output_schema": output_schema,
        "annotations": annotations,
    }
