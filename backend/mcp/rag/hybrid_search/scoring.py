"""SoAI - Hybrid search scoring and reranking [backend/mcp/rag/hybrid_search/scoring.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.types.json_value import require_json_dict
from core.validation.requirements import require_float, require_nonempty_str
from mcp.storage.search_result_parsing import (
    chunk_metadata_fields,
    distance_to_similarity,
    extract_query_results,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_final_results",
    "combine_semantic_and_bm25",
)


def combine_semantic_and_bm25(
    *,
    semantic_results: JSONDict | None,
    bm25_scores: dict[str, float],
    min_semantic_score: float,
) -> dict[str, JSONDict]:
    combined_scores: dict[str, JSONDict] = {}
    batch = extract_query_results(semantic_results)
    result_count = len(batch.ids)
    if len(batch.documents) < result_count:
        raise StateError("Semantic query documents length mismatch.")
    if len(batch.metadatas) < result_count:
        raise StateError("Semantic query metadatas length mismatch.")
    if len(batch.distances) < result_count:
        raise StateError("Semantic query distances length mismatch.")
    for index, chunk_id in enumerate(batch.ids):
        chunk_id_value = require_nonempty_str(chunk_id, field="semantic_result.chunk_id")
        chunk_metadata = require_json_dict(batch.metadatas[index], label="semantic_result.metadata")
        semantic_score = distance_to_similarity(
            require_float(batch.distances[index], field="semantic_result.distance"),
        )
        if semantic_score < min_semantic_score:
            continue
        content = require_nonempty_str(batch.documents[index], field="semantic_result.document")
        combined_scores[chunk_id_value] = {
            "content": content,
            "semantic_score": semantic_score,
            "bm25_score": bm25_scores.get(chunk_id_value, 0.0),
            **chunk_metadata_fields(chunk_metadata),
        }
    return combined_scores


def build_final_results(
    *,
    combined_scores: dict[str, JSONDict],
    semantic_weight: float,
    bm25_weight: float,
    similarity_threshold: float,
    top_k: int,
) -> list[JSONDict]:
    final_results: list[JSONDict] = []
    for data in combined_scores.values():
        semantic_score = require_float(
            data.get("semantic_score"),
            field="combined_result.semantic_score",
        )
        bm25_score = require_float(data.get("bm25_score"), field="combined_result.bm25_score")
        combined = semantic_weight * semantic_score + bm25_weight * bm25_score
        if combined >= similarity_threshold:
            final_results.append(
                {
                    "content": require_nonempty_str(
                        data.get("content"),
                        field="combined_result.content",
                    ),
                    "similarity": combined,
                    "semantic_score": semantic_score,
                    "bm25_score": bm25_score,
                    **{
                        field_name: data.get(field_name)
                        for field_name in data
                        if field_name not in ("content", "semantic_score", "bm25_score")
                    },
                },
            )
    final_results.sort(
        key=lambda item: require_float(item.get("similarity"), field="final_result.similarity"),
        reverse=True,
    )
    return final_results[:top_k]
