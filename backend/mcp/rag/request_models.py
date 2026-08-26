"""SoAI - MCP RAG request models [backend/mcp/rag/request_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("WebFetchIngestRequest",)


@dataclass(frozen=True, slots=True)
class WebFetchIngestRequest:
    conv_id: str
    user_id: int
    canonical_url: str
    normalized_focus_query: str
    normalized_strategy: str
    top_k: int
    similarity_threshold: float
    chunk_size: int
    chunk_overlap: int
    embedding_model: str
    chunking_strategy: str
    normalized_return_extract_mode: str
    return_max_chars: int
