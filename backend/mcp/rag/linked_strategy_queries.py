"""SoAI - Linked knowledge strategy-specific retrieval queries [backend/mcp/rag/linked_strategy_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.types.json import is_json_dict
from mcp.rag.hybrid_search.hybrid_search import hybrid_search
from mcp.rag.search_ops_embedding import load_collection_constraints
from mcp.storage.embeddings import generate_embeddings
from mcp.storage.search_operations import mmr_search, query_chroma_similarity_results

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = ("LinkedDocumentQuery", "LinkedRetrievalParameters", "query_linked_documents")


@dataclass(frozen=True, slots=True)
class LinkedRetrievalParameters:
    query: str
    query_embedding: list[float]
    query_embedding_model: str | None
    top_k: int
    similarity_threshold: float
    retrieval_strategy: str


@dataclass(frozen=True, slots=True)
class LinkedDocumentQuery:
    source_user_id: int
    document_ids: set[str]
    parameters: LinkedRetrievalParameters


def _with_linked_provenance(result: JSONDict, *, source_conv_id: str) -> JSONDict:
    annotated = dict(result)
    annotated["source_conv_id"] = source_conv_id
    annotated["provenance"] = "linked_knowledge"
    return annotated


async def _query_linked_similarity(
    *,
    rag: MCPRAGInternalProtocol,
    source_conv_id: str,
    request: LinkedDocumentQuery,
) -> list[JSONDict]:
    source_query_embedding = await _source_query_embedding(
        rag=rag,
        source_conv_id=source_conv_id,
        request=request,
    )
    if source_query_embedding is None:
        return []
    raw_filter = {"document_id": {"$in": sorted(request.document_ids)}}
    if not is_json_dict(raw_filter):
        raise StateError("Linked knowledge search filter is invalid.")
    where_filter: dict[str, JSONValue] = raw_filter
    results = await query_chroma_similarity_results(
        rag.storage,
        conv_id=source_conv_id,
        query_embedding=source_query_embedding,
        top_k=request.parameters.top_k,
        similarity_threshold=request.parameters.similarity_threshold,
        where_filter=where_filter,
        length_mismatch_error=StateError,
    )
    return [_with_linked_provenance(result, source_conv_id=source_conv_id) for result in results]


def _same_embedding_model(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return left.strip() == right.strip()


async def _source_query_embedding(
    *,
    rag: MCPRAGInternalProtocol,
    source_conv_id: str,
    request: LinkedDocumentQuery,
) -> list[float] | None:
    expected_dimensions, source_embedding_model = await load_collection_constraints(
        rag,
        source_conv_id,
    )
    if not _same_embedding_model(source_embedding_model, request.parameters.query_embedding_model):
        return await _generated_source_query_embedding(
            rag=rag,
            source_conv_id=source_conv_id,
            request=request,
            expected_dimensions=expected_dimensions,
            source_embedding_model=source_embedding_model,
        )
    if expected_dimensions is None or expected_dimensions <= 0:
        return request.parameters.query_embedding
    if len(request.parameters.query_embedding) == expected_dimensions:
        return request.parameters.query_embedding
    return await _generated_source_query_embedding(
        rag=rag,
        source_conv_id=source_conv_id,
        request=request,
        expected_dimensions=expected_dimensions,
        source_embedding_model=source_embedding_model,
    )


async def _generated_source_query_embedding(
    *,
    rag: MCPRAGInternalProtocol,
    source_conv_id: str,
    request: LinkedDocumentQuery,
    expected_dimensions: int | None,
    source_embedding_model: str | None,
) -> list[float] | None:
    if request.source_user_id <= 0 or not request.parameters.query.strip():
        return None
    generated = await generate_embeddings(
        rag.storage,
        [request.parameters.query],
        source_conv_id,
        user_id=request.source_user_id,
        embedding_model=source_embedding_model,
    )
    source_query_embedding = generated[0] if generated and generated[0] else None
    if source_query_embedding is None:
        return None
    if (
        expected_dimensions is not None
        and expected_dimensions > 0
        and len(source_query_embedding) != expected_dimensions
    ):
        return None
    return source_query_embedding


async def _query_linked_mmr(
    *,
    rag: MCPRAGInternalProtocol,
    source_conv_id: str,
    request: LinkedDocumentQuery,
) -> list[JSONDict]:
    source_query_embedding = await _source_query_embedding(
        rag=rag,
        source_conv_id=source_conv_id,
        request=request,
    )
    if source_query_embedding is None:
        return []
    linked_results: list[JSONDict] = []
    for document_id in sorted(request.document_ids):
        result = await mmr_search(
            rag.storage,
            source_conv_id,
            request.parameters.query,
            source_query_embedding,
            request.parameters.top_k,
            request.parameters.similarity_threshold,
            document_id=document_id,
        )
        raw_results = result.get("results")
        if not isinstance(raw_results, list):
            continue
        linked_results.extend(
            _with_linked_provenance(candidate, source_conv_id=source_conv_id)
            for candidate in raw_results
            if is_json_dict(candidate)
        )
    return linked_results


async def _query_linked_hybrid(
    *,
    rag: MCPRAGInternalProtocol,
    source_conv_id: str,
    request: LinkedDocumentQuery,
) -> list[JSONDict]:
    source_query_embedding = await _source_query_embedding(
        rag=rag,
        source_conv_id=source_conv_id,
        request=request,
    )
    if source_query_embedding is None:
        return []
    linked_results: list[JSONDict] = []
    for document_id in sorted(request.document_ids):
        result = await hybrid_search(
            rag,
            source_conv_id,
            request.parameters.query,
            request.parameters.top_k,
            request.parameters.similarity_threshold,
            user_id=request.source_user_id,
            document_id=document_id,
            _from_search=True,
            _query_embedding=source_query_embedding,
        )
        raw_results = result.get("results")
        if not isinstance(raw_results, list):
            continue
        linked_results.extend(
            _with_linked_provenance(candidate, source_conv_id=source_conv_id)
            for candidate in raw_results
            if is_json_dict(candidate)
        )
    return linked_results


async def query_linked_documents(
    *,
    rag: MCPRAGInternalProtocol,
    source_conv_id: str,
    request: LinkedDocumentQuery,
) -> list[JSONDict]:
    if request.parameters.retrieval_strategy == "hybrid":
        return await _query_linked_hybrid(
            rag=rag,
            source_conv_id=source_conv_id,
            request=request,
        )
    if request.parameters.retrieval_strategy == "mmr":
        return await _query_linked_mmr(
            rag=rag,
            source_conv_id=source_conv_id,
            request=request,
        )
    return await _query_linked_similarity(
        rag=rag,
        source_conv_id=source_conv_id,
        request=request,
    )
