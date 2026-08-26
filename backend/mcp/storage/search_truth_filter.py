"""SoAI - SQLite-truth filtering for RAG search results [backend/mcp/storage/search_truth_filter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.requirements import require_float, require_nonempty_str
from mcp.storage.search_result_parsing import (
    SearchResultBatch,
    chunk_metadata_fields,
    distance_to_similarity,
    extract_query_results,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.storage.internal_protocols import MCPStorageProtocol

__all__ = (
    "filter_chroma_query_result_by_sqlite_truth",
    "filter_similarity_results_by_sqlite_truth",
)


async def filter_similarity_results_by_sqlite_truth(
    storage: MCPStorageProtocol,
    *,
    batch: SearchResultBatch,
    similarity_threshold: float,
    length_mismatch_error: type[Exception],
) -> list[JSONDict]:
    result_count = len(batch.ids)
    if len(batch.distances) < result_count:
        raise length_mismatch_error("Chroma query distances length mismatch.")
    if len(batch.metadatas) < result_count:
        raise length_mismatch_error("Chroma query metadatas length mismatch.")
    chunk_ids = [
        require_nonempty_str(chunk_id, field="chroma_result.chunk_id") for chunk_id in batch.ids
    ]
    truth_rows = await storage.database_files.get_rag_chunks_by_ids_completed(chunk_ids)
    truth_by_id = {row["id"]: row for row in truth_rows}
    filtered: list[JSONDict] = []
    for index, chunk_id in enumerate(chunk_ids):
        truth = truth_by_id.get(chunk_id)
        if truth is None:
            continue
        similarity = distance_to_similarity(require_float(batch.distances[index], field="distance"))
        if similarity < similarity_threshold:
            continue
        filtered.append(
            {
                "content": truth["content"],
                "similarity": similarity,
                **chunk_metadata_fields(batch.metadatas[index]),
            },
        )
    return filtered


async def filter_chroma_query_result_by_sqlite_truth(
    storage: MCPStorageProtocol,
    result: JSONDict | None,
) -> JSONDict | None:
    batch = extract_query_results(result)
    if not batch.ids:
        return result
    chunk_ids = [
        require_nonempty_str(chunk_id, field="chroma_result.chunk_id") for chunk_id in batch.ids
    ]
    truth_rows = await storage.database_files.get_rag_chunks_by_ids_completed(chunk_ids)
    truth_by_id = {row["id"]: row for row in truth_rows}
    ids: list[JSONValue] = []
    documents: list[JSONValue] = []
    metadatas: list[JSONValue] = []
    distances: list[JSONValue] = []
    embeddings: list[JSONValue] = []
    for index, chunk_id in enumerate(chunk_ids):
        truth = truth_by_id.get(chunk_id)
        if truth is None:
            continue
        ids.append(chunk_id)
        documents.append(truth["content"])
        metadata = (
            chunk_metadata_fields(batch.metadatas[index]) if index < len(batch.metadatas) else {}
        )
        distance = batch.distances[index] if index < len(batch.distances) else 0.0
        metadatas.append(metadata)
        distances.append(distance)
        if index < len(batch.embeddings):
            embeddings.append(batch.embeddings[index])
    filtered: JSONDict = {
        "ids": [ids],
        "documents": [documents],
        "metadatas": [metadatas],
        "distances": [distances],
    }
    if embeddings:
        filtered["embeddings"] = [embeddings]
    return filtered
