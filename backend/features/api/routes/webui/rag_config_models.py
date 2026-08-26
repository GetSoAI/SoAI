"""SoAI - Typed response models for WebUI RAG configuration routes [backend/features/api/routes/webui/rag_config_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal, TypedDict

from core.rag.protocols import RAGConfigFields
from core.types.json import JSONDict

__all__ = (
    "RAGConversationConfigResponse",
    "RAGConversationConfigUpdateFields",
    "RAGReindexResponse",
)


class RAGConversationConfigResponse(RAGConfigFields):
    conv_id: str
    default_embedding_model: str | None


class RAGConversationConfigUpdateFields(TypedDict):
    enabled: bool | None
    retrieval_strategy: str | None
    top_k: int | None
    similarity_threshold: float | None
    chunking_strategy: str | None
    chunk_size: int | None
    chunk_overlap: int | None
    embedding_model: str | None


class RAGReindexResponse(TypedDict):
    status: Literal["queued"]
    task_id: str
    conv_id: str
    embedding_model: str
    knowledge_attachment: JSONDict
