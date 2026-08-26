"""SoAI - ChromaDB vector search with MMR reranking operations [backend/mcp/storage/search_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json import normalize_for_json
from core.types.json_value import require_json_dict
from core.validation.requirements import require_float, require_nonempty_str
from mcp.storage.internal_protocols import MCPStorageProtocol
from mcp.storage.search_result_parsing import (
    SearchResultBatch,
    chunk_metadata_fields,
    distance_to_similarity,
    extract_query_results,
)
from mcp.storage.search_truth_filter import (
    filter_chroma_query_result_by_sqlite_truth,
    filter_similarity_results_by_sqlite_truth,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SearchCandidate",
    "SearchResultBatch",
    "chunk_metadata_fields",
    "cosine_similarity",
    "distance_to_similarity",
    "extract_query_results",
    "filter_chroma_query_result_by_sqlite_truth",
    "filter_similarity_results",
    "filter_similarity_results_by_sqlite_truth",
    "mmr_search",
    "query_chroma_similarity_results",
)


@dataclass(slots=True)
class SearchCandidate:
    content: str
    similarity: float
    embedding: list[float] | None
    metadata: JSONDict


def filter_similarity_results(
    *,
    documents: list[JSONValue],
    metadatas: list[JSONValue],
    distances: list[JSONValue],
    similarity_threshold: float,
    length_mismatch_error: type[Exception],
) -> list[JSONDict]:
    document_count = len(documents)
    if len(distances) < document_count:
        raise length_mismatch_error("Chroma query distances length mismatch.")
    if len(metadatas) < document_count:
        raise length_mismatch_error("Chroma query metadatas length mismatch.")
    filtered: list[JSONDict] = []
    for index, document in enumerate(documents):
        similarity = distance_to_similarity(require_float(distances[index], field="distance"))
        if similarity < similarity_threshold:
            continue
        metadata = require_json_dict(metadatas[index], label="metadata")
        filtered.append(
            {
                "content": require_nonempty_str(document, field="document"),
                "similarity": similarity,
                **chunk_metadata_fields(metadata),
            },
        )
    return filtered


async def query_chroma_similarity_results(
    storage: MCPStorageProtocol,
    *,
    conv_id: str,
    query_embedding: list[float],
    top_k: int,
    similarity_threshold: float,
    where_filter: dict[str, JSONValue] | None,
    length_mismatch_error: type[Exception],
) -> list[JSONDict]:
    rw_lock = await storage.get_chroma_rw_lock(conv_id)
    async with rw_lock.read_lock():
        collection_name = await storage.chroma.resolve_active_collection_name(conv_id)
        query_timeout = storage.config.get_int("TOOLS.RAG.CHROMA_QUERY_TIMEOUT_SEC")
        raw_result = await storage.chroma.query(
            conv_id=conv_id,
            collection_name=collection_name,
            query_embeddings=[query_embedding],
            n_results=min(max(top_k * 3, top_k), 200),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
            timeout_sec=float(max(1, int(query_timeout))),
        )
        normalized = normalize_for_json(raw_result)
        if normalized is None:
            results = None
        else:
            results = require_json_dict(normalized, label="chroma_query_result")
    batch = extract_query_results(results)
    filtered_results = await filter_similarity_results_by_sqlite_truth(
        storage,
        batch=batch,
        similarity_threshold=similarity_threshold,
        length_mismatch_error=length_mismatch_error,
    )
    return filtered_results[:top_k]


def cosine_similarity(vector1: list[float], vector2: list[float]) -> float:
    dot_product = sum(
        (value_a * value_b for value_a, value_b in zip(vector1, vector2, strict=False)),
    )
    norm1 = math.sqrt(sum(value * value for value in vector1))
    norm2 = math.sqrt(sum(value * value for value in vector2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


async def mmr_search(
    self: MCPStorageProtocol,
    conv_id: str,
    query: str,
    query_embedding: list[float],
    top_k: int,
    similarity_threshold: float,
    document_id: str | None = None,
    lambda_mult: float = 0.5,
) -> JSONDict:
    candidates_k = min(top_k * 6, 200)

    rw_lock = await self.get_chroma_rw_lock(conv_id)
    async with rw_lock.read_lock():
        collection_name = await self.chroma.resolve_active_collection_name(conv_id)
        query_timeout = self.config.get_int("TOOLS.RAG.CHROMA_QUERY_TIMEOUT_SEC")
        where_filter: dict[str, JSONValue] | None = (
            {"document_id": document_id} if document_id else None
        )
        raw_result = await self.chroma.query(
            conv_id=conv_id,
            collection_name=collection_name,
            query_embeddings=[query_embedding],
            n_results=candidates_k,
            where=where_filter,
            include=["documents", "metadatas", "distances", "embeddings"],
            timeout_sec=float(max(1, int(query_timeout))),
        )
        normalized = normalize_for_json(raw_result)
        if normalized is None:
            results = None
        elif not isinstance(normalized, dict):
            raise StateError("Chroma query returned non-JSON data.")
        results = normalized
    batch = extract_query_results(results)
    truth_rows = await self.database_files.get_rag_chunks_by_ids_completed(
        [require_nonempty_str(chunk_id, field="mmr.chunk_id") for chunk_id in batch.ids],
    )
    truth_by_id = {row["id"]: row for row in truth_rows}
    candidates: list[SearchCandidate] = []
    for index, chunk_id in enumerate(batch.ids):
        chunk_id_value = require_nonempty_str(chunk_id, field="mmr.chunk_id")
        truth = truth_by_id.get(chunk_id_value)
        if truth is None:
            continue
        raw_metadata = batch.metadatas[index] if index < len(batch.metadatas) else None
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        raw_distance = batch.distances[index] if index < len(batch.distances) else None
        distance = float(raw_distance) if isinstance(raw_distance, int | float) else 0.0
        raw_embedding = batch.embeddings[index] if index < len(batch.embeddings) else None
        embedding: list[float] | None = None
        if isinstance(raw_embedding, list) and raw_embedding:
            numeric_values = [
                float(value) for value in raw_embedding if isinstance(value, int | float)
            ]
            if len(numeric_values) == len(raw_embedding):
                embedding = numeric_values
        candidates.append(
            SearchCandidate(
                content=truth["content"],
                similarity=distance_to_similarity(distance),
                embedding=embedding,
                metadata=chunk_metadata_fields(metadata),
            ),
        )
    selected: list[SearchCandidate] = []
    remaining = list(candidates)
    while len(selected) < top_k and remaining:
        best_score, best_index = (-float("inf"), 0)
        for remaining_index, candidate in enumerate(remaining):
            relevance = candidate.similarity
            max_sim_to_selected = 0.0
            if selected and candidate.embedding is not None:
                for selection in selected:
                    if selection.embedding is not None:
                        max_sim_to_selected = max(
                            max_sim_to_selected,
                            cosine_similarity(candidate.embedding, selection.embedding),
                        )
            mmr_score = lambda_mult * relevance - (1 - lambda_mult) * max_sim_to_selected
            if mmr_score > best_score:
                best_score, best_index = (mmr_score, remaining_index)
        best_candidate = remaining.pop(best_index)
        if best_candidate.similarity >= similarity_threshold:
            selected.append(best_candidate)
        elif not selected:
            break
    filtered_results: list[JSONDict] = []
    for result_entry in selected:
        filtered_results.append(
            {
                "content": result_entry.content,
                "similarity": result_entry.similarity,
                **result_entry.metadata,
            },
        )
    return {
        "query": query,
        "results": filtered_results,
        "count": len(filtered_results),
    }
