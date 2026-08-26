"""SoAI - Chunk storage record builders [backend/mcp/storage/chunk_storage_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib

from core.files.rag_chunk_identity import build_rag_index_chunk_id
from core.types.json import JSONDict
from mcp.rag.indexing.chunking import DocumentChunk

__all__ = ("build_chunk_records",)


def build_chunk_records(document_id: str, chunks: list[DocumentChunk]) -> list[JSONDict]:
    records: list[JSONDict] = []
    for chunk in chunks:
        records.append(
            {
                "id": build_rag_index_chunk_id(document_id, chunk.index),
                "document_id": document_id,
                "chunk_index": chunk.index,
                "content": chunk.content,
                "content_hash": hashlib.sha256(chunk.content.encode()).hexdigest(),
                "token_count": chunk.token_count,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "metadata": None,
            },
        )
    return records
