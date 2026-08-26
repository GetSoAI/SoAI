"""SoAI - MCP RAG web fetch tool definition builders [backend/mcp/rag/tool_definitions_web_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags
from core.rag.option_contracts import (
    build_chunking_strategy_property,
    build_retrieval_strategy_property,
    build_return_extract_mode_property,
)
from mcp.rag.tool_schema import (
    build_tool,
    prop_chunk_overlap,
    prop_chunk_size,
    prop_conv_id,
    prop_embedding_model,
)
from mcp.tools.icons import ICON_GLOBE

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_knowledge_web_fetch_tool",
    "build_web_fetch_tool",
)


def build_web_fetch_tool() -> JSONDict:
    return build_tool(
        title="Web Fetch",
        icon_src=ICON_GLOBE,
        description="Fetch a URL over HTTP and extract readable content (extraction does not run JavaScript). Attempts a screenshot using the browser runtime for quick inspection. For JS-rendered pages, login-required pages, or blocked/empty responses, use the real-browser tools instead.",
        input_properties={
            "url": {"type": "string", "description": "URL to fetch"},
            "extract_mode": build_return_extract_mode_property(),
            "screenshot": {
                "type": "boolean",
                "description": "If false, skip screenshot capture.",
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Hard timeout for the full fetch operation.",
                "minimum": 1,
                "maximum": 300000,
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return in content fields (truncates when exceeded).",
                "minimum": 1000,
                "maximum": 500000,
            },
        },
        required=["url"],
        output_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "final_url": {"type": "string"},
                "title": {"type": "string"},
                "content_type": {"type": "string"},
                "extract_mode": {"type": "string"},
                "truncated": {"type": "boolean"},
                "max_chars": {"type": "integer"},
                "length": {"type": "integer"},
                "raw_length": {"type": "integer"},
                "took_ms": {"type": "integer"},
                "fetched_at": {"type": "string"},
                "content": {"type": "string"},
                "page_count": {"type": ["integer", "null"]},
                "persisted": {"type": "boolean"},
                "read_document_hint": {"type": "string"},
                "read_document_args": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "max_chars": {"type": "integer"},
                        "offset_chars": {"type": "integer"},
                        "parse_timeout_sec": {"type": "integer"},
                    },
                },
                "browser_navigate_hint": {"type": "string"},
                "browser_navigate_args": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "url": {"type": "string"},
                        "include_snapshot": {"type": "boolean"},
                        "profile": {"type": "string"},
                        "session_scope": {"type": "string"},
                    },
                },
                "browser_downloads_hint": {"type": "string"},
                "browser_downloads_args": {
                    "type": "object",
                    "properties": {
                        "profile": {"type": "string"},
                        "session_scope": {"type": "string"},
                    },
                },
                "screenshot": {
                    "type": "object",
                    "properties": {
                        "content_type": {"type": "string"},
                        "image_base64": {"type": "string"},
                    },
                },
                "screenshot_error": {"type": "string"},
            },
        },
        annotations=build_tool_annotation_flags(open_world=True),
    )


def build_knowledge_web_fetch_tool(*, fetch_result_properties: JSONDict) -> JSONDict:
    return build_tool(
        title="Web Fetch (RAG Ingest)",
        icon_src=ICON_GLOBE,
        description="Fetch a URL over HTTP and ingest it into the conversation knowledge base (embeddings + immediate context). Attempts a screenshot using the browser runtime for quick inspection. If the page is JS-rendered, requires login, or is blocked/empty via HTTP fetch, use the real-browser tools (browser_navigate + browser_snapshot/browser_eval) instead.",
        input_properties={
            "conv_id": prop_conv_id(),
            "url": {"type": "string", "description": "URL to fetch and ingest"},
            "extract_mode": build_return_extract_mode_property(),
            "screenshot": {
                "type": "boolean",
                "description": "If false, skip screenshot capture.",
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Hard timeout for the full fetch operation.",
                "minimum": 1,
                "maximum": 300000,
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return in content fields (truncates when exceeded).",
                "minimum": 1000,
                "maximum": 500000,
            },
            "focus_query": {
                "type": "string",
                "description": "Optional query used to retrieve immediate context from this URL. If omitted/empty, immediate context is selected from the fetched document without query conditioning.",
            },
            "retrieval_strategy": build_retrieval_strategy_property(
                description="Retrieval strategy for immediate context: similarity, mmr, or hybrid",
            ),
            "top_k": {
                "type": "integer",
                "description": "Number of immediate context results to return (bounded by configured fetch context limit)",
            },
            "similarity_threshold": {
                "type": "number",
                "description": "Minimum similarity score for immediate context results (0.0-1.0)",
            },
            "chunking_strategy": build_chunking_strategy_property(),
            "chunk_size": prop_chunk_size(),
            "chunk_overlap": prop_chunk_overlap(),
            "embedding_model": prop_embedding_model(),
        },
        required=["url"],
        output_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "final_url": {"type": "string"},
                "title": {"type": "string"},
                "content_type": {"type": "string"},
                "extract_mode": {"type": "string"},
                "truncated": {"type": "boolean"},
                "max_chars": {"type": "integer"},
                "length": {"type": "integer"},
                "raw_length": {"type": "integer"},
                "took_ms": {"type": "integer"},
                "fetched_at": {"type": "string"},
                "content": {"type": "string"},
                "page_count": {"type": ["integer", "null"]},
                "persisted": {"type": "boolean"},
                "document_id": {"type": "string"},
                "task_id": {"type": "string"},
                "status": {"type": "string"},
                "status_message": {"type": "string"},
                "poll_interval_ms": {"type": "integer"},
                "ttl": {"type": "integer"},
                "read_document_hint": {"type": "string"},
                "read_document_args": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "max_chars": {"type": "integer"},
                        "offset_chars": {"type": "integer"},
                        "parse_timeout_sec": {"type": "integer"},
                    },
                },
                "browser_navigate_hint": {"type": "string"},
                "browser_navigate_args": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "include_snapshot": {"type": "boolean"},
                        "profile": {"type": "string"},
                        "session_scope": {"type": "string"},
                    },
                },
                "browser_downloads_hint": {"type": "string"},
                "browser_downloads_args": {
                    "type": "object",
                    "properties": {
                        "profile": {"type": "string"},
                        "session_scope": {"type": "string"},
                    },
                },
                "result": {
                    "type": "object",
                    "properties": fetch_result_properties,
                },
                "background_task": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "status": {"type": "string"},
                        "result": {
                            "type": "object",
                            "properties": fetch_result_properties,
                        },
                    },
                },
                "screenshot": {
                    "type": "object",
                    "properties": {
                        "content_type": {"type": "string"},
                        "image_base64": {"type": "string"},
                    },
                },
                "screenshot_error": {"type": "string"},
            },
        },
        annotations=build_tool_annotation_flags(open_world=True),
    )
