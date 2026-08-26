"""SoAI - RAG cross-subsystem protocols and shared typed contracts [backend/core/rag/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal, Protocol, TypedDict

from core.rag.knowledge_prompt_types import (
    KnowledgePromptClaimResult,
    KnowledgePromptEventRecord,
    KnowledgePromptProjectionInputs,
)
from core.types.json import JSONDict

__all__ = (
    "DatabaseKnowledgePromptStateProtocol",
    "RAGConfigFields",
)


class RAGConfigFields(TypedDict):
    retrieval_strategy: str
    enabled: bool
    embedding_model: str | None
    similarity_threshold: float
    top_k: int
    chunking_strategy: str
    chunk_overlap: int
    chunk_size: int


class DatabaseKnowledgePromptStateProtocol(Protocol):
    async def record_knowledge_event(
        self,
        *,
        conv_id: str,
        user_id: int,
        event_type: Literal[
            "documents_added",
            "documents_removed",
            "document_processing_completed",
            "document_processing_failed",
            "document_processing_cancelled",
            "knowledge_reindex_queued",
            "knowledge_reindex_completed",
            "knowledge_reindex_failed",
            "knowledge_reindex_cancelled",
        ],
        document_names: tuple[str, ...],
        document_count: int,
        details: JSONDict,
        created_at_ms: int,
    ) -> KnowledgePromptEventRecord: ...

    async def load_prompt_projection_inputs(
        self,
        *,
        conv_id: str,
        user_id: int,
        max_pending_events: int,
        max_documents: int,
    ) -> KnowledgePromptProjectionInputs: ...

    async def create_or_reuse_delivery_claim(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str,
        claim_id: str,
        event_ceiling_id: int,
        state_signature: str,
        expires_at_ms: int,
        now_ms: int,
    ) -> KnowledgePromptClaimResult: ...

    async def commit_active_claim(
        self,
        *,
        conv_id: str,
        user_id: int,
        claim_id: str,
        request_id: str,
        event_ceiling_id: int,
        state_signature: str,
        delivered_at_ms: int,
    ) -> bool: ...

    async def release_active_claim(
        self,
        *,
        conv_id: str,
        user_id: int,
        claim_id: str,
        request_id: str,
    ) -> bool: ...
