"""SoAI - MCP RAG resource and tool handlers [backend/mcp/handlers/resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sized
from re import Pattern
from typing import TYPE_CHECKING

from core.files.protocols import DatabaseFilesProtocol
from core.mcp.content_envelopes import (
    build_json_resource_content,
    build_resource_contents_result,
)
from core.mcp.protocols_rag import MCPRAGProtocol
from core.types.json_value import is_json_value
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.files.database_types import RAGChunkRecord, RAGDocumentRecord
    from core.types.json import JSONDict, JSONValue

    type RagResourceData = (
        JSONValue
        | list[RAGDocumentRecord]
        | RAGDocumentRecord
        | list[RAGChunkRecord]
        | RAGChunkRecord
        | None
    )

__all__ = ("read_rag_resource_uri",)

_RESOURCE_PAGE_LIMIT = 500
_RESOURCE_CHUNK_LIMIT = 500


def _validate_rag_uuid(value: str) -> None:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError) as exception:
        raise MCPJSONRPCError(-32602, f"Invalid UUID format: {value}") from exception


async def _handle_rag_resource(
    *,
    uri_type: str,
    id_val: str,
    data_awaitable: Awaitable[RagResourceData],
    key: str | None = None,
    items_key: str | None = None,
) -> JSONDict:
    if uri_type in ("documents", "chunks"):
        _validate_rag_uuid(id_val)
    raw_data = await data_awaitable
    if raw_data is None:
        label = {
            "conversations": "Conversation",
            "documents": "Document",
            "chunks": "Chunk",
        }.get(uri_type, "Resource")
        raise MCPJSONRPCError(-32602, f"{label} not found: {id_val}")
    if not is_json_value(raw_data):
        raise MCPJSONRPCError(-32603, f"Invalid {uri_type} resource payload: expected JSON value")
    data: JSONValue = raw_data
    if key and items_key is not None:
        if not isinstance(data, Sized):
            raise MCPJSONRPCError(
                -32603,
                f"Invalid {uri_type} resource payload: expected sized collection",
            )
        data = {key: id_val, items_key: data, "count": len(data)}
    uri_suffix = f"/{items_key}" if items_key else ""
    return build_resource_contents_result(
        build_json_resource_content(
            uri=f"soai://rag/{uri_type.replace('_', '/')}/{id_val}{uri_suffix}",
            payload=data,
        ),
    )


async def read_rag_resource_uri(
    *,
    uri: str,
    user_id: int,
    patterns: dict[str, Pattern[str]],
    require_rag: Callable[[], MCPRAGProtocol],
    require_rag_user_authorization: Callable[[str, int, str], Awaitable[tuple[str, int]]],
    require_rag_document_authorization: Callable[[str, int, str], Awaitable[tuple[JSONDict, int]]],
    database_files: DatabaseFilesProtocol,
) -> JSONDict:
    rag = require_rag()
    if not patterns:
        raise MCPJSONRPCError(-32603, "RAG resources are not initialized")
    for pattern_name, pattern in patterns.items():
        match = pattern.match(uri)
        if not match:
            continue
        groups = match.groupdict()
        if pattern_name == "conversations_documents":
            resolved_id, _ = await require_rag_user_authorization(
                groups["conv_id"],
                user_id,
                "conversation document access",
            )
            return await _handle_rag_resource(
                uri_type="conversations",
                id_val=resolved_id,
                data_awaitable=database_files.get_rag_documents_for_conversation_with_active_links(
                    resolved_id,
                    user_id,
                    limit=_RESOURCE_PAGE_LIMIT,
                ),
                key="conv_id",
                items_key="documents",
            )
        if pattern_name == "conversations_config":
            resolved_id, _ = await require_rag_user_authorization(
                groups["conv_id"],
                user_id,
                "conversation config access",
            )

            async def _load_config(
                conv_id: str = resolved_id,
            ) -> JSONValue:
                data = await database_files.get_rag_config(conv_id)
                if data is None:
                    return {}
                if not is_json_value(data):
                    raise MCPJSONRPCError(-32603, "Invalid stored RAG config payload")
                return data

            return await _handle_rag_resource(
                uri_type="conversations",
                id_val=resolved_id,
                data_awaitable=_load_config(),
                items_key="config",
            )
        if pattern_name == "conversations_collections":
            resolved_id, _ = await require_rag_user_authorization(
                groups["conv_id"],
                user_id,
                "conversation collections access",
            )
            return await _handle_rag_resource(
                uri_type="conversations",
                id_val=resolved_id,
                data_awaitable=rag.get_collection_metadata(resolved_id),
                items_key="collections",
            )
        if pattern_name == "document":
            document_id = groups["document_id"]
            _validate_rag_uuid(document_id)
            await require_rag_document_authorization(document_id, user_id, "document access")
            return await _handle_rag_resource(
                uri_type="documents",
                id_val=document_id,
                data_awaitable=database_files.get_rag_document_by_id(document_id),
            )
        if pattern_name == "document_chunks":
            document_id = groups["document_id"]
            _validate_rag_uuid(document_id)
            await require_rag_document_authorization(document_id, user_id, "document chunks access")
            return await _handle_rag_resource(
                uri_type="documents",
                id_val=document_id,
                data_awaitable=database_files.get_rag_chunks_for_document_page(
                    document_id,
                    limit=_RESOURCE_CHUNK_LIMIT,
                ),
                key="document_id",
                items_key="chunks",
            )
        if pattern_name == "chunk":
            chunk_id = groups["chunk_id"]
            _validate_rag_uuid(chunk_id)
            chunk = await database_files.get_rag_chunk_by_id(chunk_id)
            if not chunk:
                raise MCPJSONRPCError(-32602, f"Chunk not found: {chunk_id}")
            if not isinstance(chunk, dict):
                raise MCPJSONRPCError(-32603, "Invalid chunk data")
            doc_id = chunk.get("document_id")
            if not doc_id:
                raise MCPJSONRPCError(-32602, f"Chunk has no document_id: {chunk_id}")
            await require_rag_document_authorization(str(doc_id), user_id, "chunk access")
            return await _handle_rag_resource(
                uri_type="chunks",
                id_val=chunk_id,
                data_awaitable=database_files.get_rag_chunk_by_id(chunk_id),
            )
        raise MCPJSONRPCError(-32602, f"Handler not found: rag_resource:{pattern_name}")
    raise MCPJSONRPCError(-32602, f"Unknown RAG resource URI: {uri}")
