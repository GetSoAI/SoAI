"""SoAI - Chunk storage disk reservation size planning [backend/mcp/storage/chunk_storage_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence

from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict

__all__ = (
    "encoded_chroma_vector_payload_size",
    "encoded_chunk_database_payload_size",
    "encoded_sparse_index_payload_size",
)


def _encoded_json_size(payload: JSONDict) -> int:
    return len(serialize_json_compact_stable_strict(payload, ensure_ascii=False).encode("utf-8"))


def encoded_chroma_vector_payload_size(
    *,
    ids: Sequence[str],
    embeddings: Sequence[Sequence[float]],
    documents: Sequence[str],
    metadatas: Sequence[JSONDict],
) -> int:
    return _encoded_json_size(
        {
            "ids": list(ids),
            "embeddings": [list(embedding) for embedding in embeddings],
            "documents": list(documents),
            "metadatas": [dict(metadata) for metadata in metadatas],
        },
    )


def encoded_chunk_database_payload_size(
    *,
    ids: Sequence[str],
    chunks: Sequence[JSONDict],
    embedding_model: str,
    effective_model: str,
    embedding_dimensions: int,
) -> int:
    return _encoded_json_size(
        {
            "ids": list(ids),
            "chunks": [dict(chunk) for chunk in chunks],
            "embedding_model": embedding_model,
            "effective_model": effective_model,
            "embedding_dimensions": int(embedding_dimensions),
        },
    )


def encoded_sparse_index_payload_size(*, documents: Sequence[tuple[str, str]]) -> int:
    return _encoded_json_size(
        {
            "documents": [
                {"id": document_id, "content": content} for document_id, content in documents
            ],
        },
    )
