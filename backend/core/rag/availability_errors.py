"""SoAI - Actionable knowledge indexing prerequisites [backend/core/rag/availability_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload

__all__ = (
    "build_documents_not_indexed_error",
    "build_embedding_model_unavailable_error",
    "require_indexed_document_count",
)


def require_indexed_document_count(counts: dict[str, int]) -> int:
    completed_count_value = counts.get("completed") if isinstance(counts, dict) else 0
    completed_count = completed_count_value if isinstance(completed_count_value, int) else 0
    if completed_count <= 0:
        raise build_documents_not_indexed_error()
    return completed_count


def build_embedding_model_unavailable_error() -> ValidationError:
    message = "No embedding model is available. Select an embedding model in Chat settings, or install an embedding backend and download a model, then try again."
    error = ValidationError(message)
    apply_public_error_payload(
        error, ErrorPublicPayload(code="rag_embedding_model_unavailable", message=message)
    )
    return error


def build_documents_not_indexed_error() -> ValidationError:
    message = "No indexed knowledge is available to reindex. Upload and index a document first."
    error = ValidationError(message)
    apply_public_error_payload(
        error, ErrorPublicPayload(code="rag_documents_not_indexed", message=message)
    )
    return error
