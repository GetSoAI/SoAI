"""SoAI - RAG search result parsing primitives [backend/mcp/storage/search_result_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SearchResultBatch",
    "chunk_metadata_fields",
    "distance_to_similarity",
    "extract_query_results",
)


@dataclass(slots=True)
class SearchResultBatch:
    ids: list[JSONValue]
    documents: list[JSONValue]
    metadatas: list[JSONValue]
    distances: list[JSONValue]
    embeddings: list[JSONValue]


def distance_to_similarity(distance: float) -> float:
    try:
        value = float(distance)
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, min(1.0, 1 - value / 2))


def extract_query_results(
    results: JSONDict | None,
) -> SearchResultBatch:
    if not isinstance(results, dict) or not results:
        return SearchResultBatch([], [], [], [], [])

    def _ensure_list(value: JSONValue) -> list[JSONValue]:
        return value if isinstance(value, list) else []

    def _unwrap_first(values: list[JSONValue]) -> list[JSONValue]:
        if not values:
            return []
        first = values[0]
        if isinstance(first, list):
            return list(first)
        return values

    ids = _unwrap_first(_ensure_list(results.get("ids")))
    documents = _unwrap_first(_ensure_list(results.get("documents")))
    metadatas = _unwrap_first(_ensure_list(results.get("metadatas")))
    distances = _unwrap_first(_ensure_list(results.get("distances")))
    embeddings = _unwrap_first(_ensure_list(results.get("embeddings")))
    if not ids or not documents:
        return SearchResultBatch([], [], [], [], [])
    return SearchResultBatch(
        ids,
        documents,
        metadatas if metadatas and metadatas else [],
        distances if distances and distances else [],
        embeddings if embeddings and embeddings else [],
    )


def chunk_metadata_fields(metadata: JSONValue) -> JSONDict:
    if not isinstance(metadata, dict):
        return {"document_id": "unknown", "chunk_index": 0}
    out: JSONDict = {
        "document_id": metadata.get("document_id", "unknown"),
        "chunk_index": metadata.get("chunk_index", 0),
    }
    for key in (
        "filename",
        "file_type",
        "source_type",
        "source_url",
        "start_char",
        "end_char",
        "token_count",
    ):
        if key in metadata:
            out[key] = metadata.get(key)
    return out
