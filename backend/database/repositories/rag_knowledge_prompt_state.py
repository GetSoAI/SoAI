"""SoAI - RAG Knowledge prompt state repository [backend/database/repositories/rag_knowledge_prompt_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from core.rag.knowledge_prompt_types import (
    KnowledgePromptClaimResult,
    KnowledgePromptEventRecord,
    KnowledgePromptProjectionInputs,
)
from database.repositories.rag_knowledge_prompt_queries import (
    load_prompt_projection_inputs_query,
)
from database.repositories.rag_knowledge_prompt_writes import (
    sync_commit_active_claim,
    sync_create_or_reuse_delivery_claim,
    sync_record_knowledge_event,
    sync_release_active_claim,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseKnowledgePromptState",)


class DatabaseKnowledgePromptState:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

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
    ) -> KnowledgePromptEventRecord:
        return await self.core.writer.queue_write_operation(
            sync_record_knowledge_event,
            conv_id,
            user_id,
            event_type,
            list(document_names),
            document_count,
            details,
            created_at_ms,
        )

    async def load_prompt_projection_inputs(
        self,
        *,
        conv_id: str,
        user_id: int,
        max_pending_events: int,
        max_documents: int,
    ) -> KnowledgePromptProjectionInputs:
        return await self.core.reader.execute_read(
            load_prompt_projection_inputs_query,
            conv_id=conv_id,
            user_id=user_id,
            max_pending_events=max_pending_events,
            max_documents=max_documents,
        )

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
    ) -> KnowledgePromptClaimResult:
        return await self.core.writer.queue_write_operation(
            sync_create_or_reuse_delivery_claim,
            conv_id,
            user_id,
            request_id,
            claim_id,
            event_ceiling_id,
            state_signature,
            expires_at_ms,
            now_ms,
        )

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
    ) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_commit_active_claim,
            conv_id,
            user_id,
            claim_id,
            request_id,
            event_ceiling_id,
            state_signature,
            delivered_at_ms,
        )

    async def release_active_claim(
        self,
        *,
        conv_id: str,
        user_id: int,
        claim_id: str,
        request_id: str,
    ) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_release_active_claim,
            conv_id,
            user_id,
            claim_id,
            request_id,
        )
