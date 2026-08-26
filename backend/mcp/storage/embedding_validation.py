"""SoAI - MCP embedding shape validation [backend/mcp/storage/embedding_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("validate_embeddings_shape",)


def validate_embeddings_shape(
    embeddings: list[list[float]],
    expected_count: int | None = None,
) -> int:
    if expected_count is not None and len(embeddings) != expected_count:
        raise ValidationError(
            f"Embeddings count mismatch: got {len(embeddings)}, expected {expected_count}",
        )
    if not embeddings:
        raise ValidationError("Embeddings list is empty")
    dims: int | None = None
    for embedding_vector in embeddings:
        if not isinstance(embedding_vector, list) or not embedding_vector:
            raise ValidationError("Invalid embedding: must be a non-empty list")
        if dims is None:
            dims = len(embedding_vector)
            if dims <= 0:
                raise ValidationError("Invalid embedding: zero-length vector")
        elif len(embedding_vector) != dims:
            raise ValidationError(
                f"Embedding dimensions mismatch within batch: expected {dims}, got {len(embedding_vector)}",
            )
    if dims is None:
        raise ValidationError("No embeddings processed.")
    return dims
