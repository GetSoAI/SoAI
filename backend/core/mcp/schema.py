"""SoAI - Core MCP schema types [backend/core/mcp/schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from re import Pattern
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "MCPResourceURIDefinition",
    "build_id_list_schema",
    "build_id_property_schema",
    "build_rag_resource_uri_definitions",
    "build_search_results_schema",
    "build_title_property_schema",
    "build_tool_annotation_flags",
    "build_tool_icon_entry",
    "get_rag_uri_patterns",
    "is_auto_embedding_model_selector",
    "is_auto_embedding_model_sentinel",
)

AUTO_EMBEDDING_MODEL_SELECTOR: str = "__soai_auto_embedding__"


def build_id_property_schema() -> JSONDict:
    return {"id": {"type": "string"}}


def build_title_property_schema() -> JSONDict:
    return {"title": {"type": "string"}}


def build_tool_icon_entry(icon_src: str, *, include_size: bool = True) -> JSONDict:
    icon_entry: JSONDict = {"src": icon_src, "mimeType": "image/svg+xml"}
    if include_size:
        icon_entry["sizes"] = ["24x24"]
    return icon_entry


def build_tool_annotation_flags(
    *,
    read_only: bool = False,
    destructive: bool = False,
    idempotent: bool = False,
    open_world: bool = False,
    requires_approval: bool | None = None,
) -> dict[str, bool]:
    annotations: dict[str, bool] = {
        "readOnlyHint": read_only,
        "destructiveHint": destructive,
        "idempotentHint": idempotent,
        "openWorldHint": open_world,
    }
    if requires_approval is not None:
        annotations["requiresApprovalHint"] = requires_approval
    return annotations


def build_search_results_schema(
    item_properties: Mapping[str, JSONValue],
) -> JSONDict:
    return {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "results": {
                "type": "array",
                "items": {"type": "object", "properties": item_properties},
            },
            "count": {"type": "integer"},
        },
    }


def is_auto_embedding_model_selector(value: JSONValue) -> bool:
    return is_auto_embedding_model_sentinel(value) or (
        isinstance(value, str) and value.strip().lower() == "auto"
    )


def is_auto_embedding_model_sentinel(value: JSONValue) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower() == AUTO_EMBEDDING_MODEL_SELECTOR.lower()


def build_id_list_schema(item_properties: Mapping[str, JSONValue]) -> JSONDict:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {**build_id_property_schema(), **dict(item_properties)},
        },
    }


@dataclass(frozen=True, slots=True)
class MCPResourceURIDefinition:
    name: str
    uri_template: str
    description: str
    title: str
    display_name: str
    icon_name: str
    mime_type: str = "application/json"
    audience: tuple[str, ...] = ("user", "assistant")
    priority: float = 0.5

    @property
    def regex_pattern(self) -> str:
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", self.uri_template)
        return f"^{pattern}$"

    def compile_pattern(self) -> Pattern[str]:
        return re.compile(self.regex_pattern)


def build_rag_resource_uri_definitions() -> tuple[MCPResourceURIDefinition, ...]:
    return (
        MCPResourceURIDefinition(
            name="conversations_documents",
            uri_template="soai://rag/conversations/{conv_id}/documents",
            display_name="RAG Documents for Conversation",
            title="RAG Documents",
            description="List all documents in a conversation's RAG knowledge base",
            icon_name="doc",
            audience=("user", "assistant"),
            priority=0.7,
        ),
        MCPResourceURIDefinition(
            name="conversations_config",
            uri_template="soai://rag/conversations/{conv_id}/config",
            display_name="RAG Configuration",
            title="RAG Config",
            description="Get RAG configuration for a conversation",
            icon_name="settings",
            audience=("user", "assistant"),
            priority=0.6,
        ),
        MCPResourceURIDefinition(
            name="conversations_collections",
            uri_template="soai://rag/conversations/{conv_id}/collections",
            display_name="RAG Vector Collections",
            title="RAG Collections",
            description="Get ChromaDB collection metadata for a conversation",
            icon_name="database",
            audience=("assistant",),
            priority=0.5,
        ),
        MCPResourceURIDefinition(
            name="document",
            uri_template="soai://rag/documents/{document_id}",
            display_name="RAG Document Details",
            title="RAG Document",
            description="Get details for a specific RAG document",
            icon_name="doc",
            audience=("user", "assistant"),
            priority=0.6,
        ),
        MCPResourceURIDefinition(
            name="document_chunks",
            uri_template="soai://rag/documents/{document_id}/chunks",
            display_name="RAG Document Chunks",
            title="Document Chunks",
            description="List all chunks for a RAG document",
            icon_name="database",
            audience=("assistant",),
            priority=0.5,
        ),
        MCPResourceURIDefinition(
            name="chunk",
            uri_template="soai://rag/chunks/{chunk_id}",
            display_name="RAG Chunk Details",
            title="RAG Chunk",
            description="Get details for a specific chunk",
            icon_name="database",
            audience=("assistant",),
            priority=0.4,
        ),
    )


def get_rag_uri_patterns() -> dict[str, Pattern[str]]:
    return {
        definition.name: definition.compile_pattern()
        for definition in build_rag_resource_uri_definitions()
    }
