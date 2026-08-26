"""SoAI - RAG chunk index identity helpers [backend/core/files/rag_chunk_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

__all__ = (
    "RAGIndexChunkIdentity",
    "build_rag_index_chunk_id",
    "build_rag_index_chunk_id_prefix",
    "parse_rag_index_chunk_id",
)

_CHUNK_ID_SEPARATOR = "_chunk_"


@dataclass(frozen=True, slots=True)
class RAGIndexChunkIdentity:
    document_id: str
    chunk_index: int


def build_rag_index_chunk_id(document_id: str, chunk_index: int) -> str:
    normalized_document_id = document_id.strip()
    if not normalized_document_id:
        raise ValidationError("document_id is required for RAG chunk id.")
    if not is_strict_int(chunk_index) or chunk_index < 0:
        raise ValidationError("chunk_index must be a non-negative integer.")
    return f"{normalized_document_id}{_CHUNK_ID_SEPARATOR}{chunk_index}"


def build_rag_index_chunk_id_prefix(document_id: str) -> str:
    normalized_document_id = document_id.strip()
    if not normalized_document_id:
        raise ValidationError("document_id is required for RAG chunk id prefix.")
    return f"{normalized_document_id}{_CHUNK_ID_SEPARATOR}"


def parse_rag_index_chunk_id(chunk_id: str) -> RAGIndexChunkIdentity:
    parts = chunk_id.rsplit(_CHUNK_ID_SEPARATOR, 1)
    if len(parts) != 2 or not parts[0] or not parts[1].isdigit():
        raise ValidationError(f"Invalid chunk_id format: {chunk_id}")
    return RAGIndexChunkIdentity(document_id=parts[0], chunk_index=int(parts[1]))
