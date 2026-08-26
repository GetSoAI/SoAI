"""SoAI - MCP RAG tool schema builders [backend/mcp/rag/tool_definitions_schemas.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_fetch_result_properties",
    "build_immediate_context_schema",
    "build_ingest_limits_schema",
    "build_output_limits_schema",
    "build_rag_search_result_properties",
)


def build_rag_search_result_properties() -> dict[str, JSONValue]:
    return {
        "content": {"type": "string"},
        "similarity": {"type": "number"},
        "document_id": {"type": "string"},
        "chunk_index": {"type": "integer"},
        "source_type": {"type": "string"},
        "source_url": {"type": "string"},
    }


def build_immediate_context_schema(
    rag_search_result_properties: dict[str, JSONValue],
) -> JSONDict:
    return {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "retrieval_strategy": {"type": "string"},
            "count": {"type": "integer"},
            "results": {
                "type": "array",
                "items": {"type": "object", "properties": rag_search_result_properties},
            },
        },
    }


def build_output_limits_schema() -> JSONDict:
    return {
        "type": "object",
        "properties": {
            "max_passage_chars": {"type": "integer"},
            "max_total_chars": {"type": "integer"},
            "truncated": {"type": "boolean"},
        },
    }


def build_ingest_limits_schema() -> JSONDict:
    return {
        "type": "object",
        "properties": {
            "original_chars": {"type": "integer"},
            "ingested_chars": {"type": "integer"},
            "max_content_chars": {"type": "integer"},
            "truncated": {"type": "boolean"},
        },
    }


def build_fetch_result_properties(
    *,
    immediate_context_schema: JSONDict,
    output_limits_schema: JSONDict,
    ingest_limits_schema: JSONDict,
) -> JSONDict:
    return {
        "chunks_created": {"type": "integer"},
        "processing_time_ms": {"type": "integer"},
        "fetched_content_type": {"type": "string"},
        "fetched_title": {"type": "string"},
        "fetched_source_url": {"type": "string"},
        "content": {"type": "string"},
        "content_type": {"type": "string"},
        "extract_mode": {"type": "string"},
        "truncated": {"type": "boolean"},
        "max_chars": {"type": "integer"},
        "length": {"type": "integer"},
        "raw_length": {"type": "integer"},
        "page_count": {"type": ["integer", "null"]},
        "immediate_context": immediate_context_schema,
        "output_limits": output_limits_schema,
        "ingest_limits": ingest_limits_schema,
    }
