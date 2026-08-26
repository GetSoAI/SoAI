"""SoAI - Chroma semantic query for hybrid search [backend/mcp/rag/hybrid_search/semantic_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import normalize_for_json
from core.types.json_value import require_json_dict
from mcp.storage.search_operations import filter_chroma_query_result_by_sqlite_truth

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.rag.internal_protocols import MCPRAGSearchContextProtocol

__all__ = ("run_semantic_query",)


async def run_semantic_query(
    self: MCPRAGSearchContextProtocol,
    *,
    conv_id: str,
    query_embedding: list[float],
    top_k: int,
    candidate_multiplier: int,
    document_id: str | None,
) -> JSONDict | None:
    rw_lock = await self.storage.get_chroma_rw_lock(conv_id)
    async with rw_lock.read_lock():
        collection_name = await self.storage.chroma.resolve_active_collection_name(conv_id)
        query_timeout = self.storage.config.get_int("TOOLS.RAG.CHROMA_QUERY_TIMEOUT_SEC")
        where_filter: dict[str, JSONValue] | None = (
            {"document_id": document_id} if document_id else None
        )
        raw_result = await self.storage.chroma.query(
            conv_id=conv_id,
            collection_name=collection_name,
            query_embeddings=[query_embedding],
            n_results=top_k * candidate_multiplier,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
            timeout_sec=float(max(1, int(query_timeout))),
        )
        normalized = normalize_for_json(raw_result)
        if normalized is None:
            return None
        result = require_json_dict(normalized, label="chroma_semantic_query_result")
    return await filter_chroma_query_result_by_sqlite_truth(self.storage, result)
