"""SoAI - MCP RAG ingestion request validation helpers [backend/mcp/rag/ingestion_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import unquote, urlparse

from core.errors.exceptions import ValidationError
from core.rag.parameter_validation import (
    normalize_retrieval_strategy,
    normalize_return_extract_mode,
    validate_return_max_chars,
    validate_similarity_threshold,
    validate_top_k,
)
from mcp.rag.configuration import validate_chunking_params
from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "derive_filename_from_url",
    "normalize_and_validate_web_fetch_ingest_request",
)


def derive_filename_from_url(url: str) -> str:
    normalized_url = str(url or "").strip()
    if not normalized_url:
        raise ValidationError("URL filename derivation failed: url must be a non-empty string.")
    parsed = urlparse(normalized_url)
    netloc = str(parsed.netloc or "").strip()
    path = unquote(str(parsed.path or "")).strip()
    if netloc and path and path != "/":
        filename = f"{netloc}{path}"
    elif netloc:
        filename = netloc
    else:
        filename = normalized_url
    filename = filename.strip()
    if not filename:
        raise ValidationError("URL filename derivation failed: derived filename is empty.")
    return filename


def normalize_and_validate_web_fetch_ingest_request(
    *,
    rag_service: MCPRAGInternalProtocol,
    focus_query: str,
    retrieval_strategy: str,
    top_k: int,
    similarity_threshold: float,
    chunk_size: int,
    chunk_overlap: int,
    chunking_strategy: str,
    return_extract_mode: str,
    return_max_chars: int,
) -> tuple[str, str, str, int]:
    normalized_focus_query = str(focus_query or "").strip()
    normalized_strategy = normalize_retrieval_strategy(retrieval_strategy)
    normalized_return_extract_mode = normalize_return_extract_mode(return_extract_mode)
    max_chars = validate_return_max_chars(return_max_chars)
    validate_top_k(top_k)
    validate_similarity_threshold(similarity_threshold)
    validate_chunking_params(rag_service, chunk_size, chunk_overlap, chunking_strategy)
    return normalized_focus_query, normalized_strategy, normalized_return_extract_mode, max_chars
