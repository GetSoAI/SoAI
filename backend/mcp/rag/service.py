"""SoAI - MCP RAG engine service [backend/mcp/rag/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.logging.trace import get_logger
from core.timing.constants import SHORT_POLL_INTERVAL_SEC
from core.types.json import JSONDict
from mcp.rag import conversation, deletion, reindexing, search_ops
from mcp.rag.dependencies import MCPRAGDependencies
from mcp.rag.document_upload import upload_document, upload_document_from_path
from mcp.rag.embedding_model import (
    ensure_any_embedding_model_available_with_cache,
    is_embedding_model_available_with_cache,
    validate_requested_embedding_model,
)
from mcp.rag.hybrid_search import hybrid_search
from mcp.rag.ingestion import web_fetch_ingest
from mcp.rag.runtime_components import build_rag_runtime_components
from mcp.storage.internal_protocols import MCPStorageProtocol

__all__ = ("MCPRAG",)

LOGGER_NAME = "SoAI.mcp.rag.service"


class MCPRAG:

    def __init__(self, deps: MCPRAGDependencies) -> None:
        self.database_files = deps.database_files
        self.database_conversation_knowledge_attachments = (
            deps.database_conversation_knowledge_attachments
        )
        self.database_knowledge_prompt_state = deps.database_knowledge_prompt_state
        self.database_users = deps.database_users
        self.database_conversations = deps.database_conversations
        self.event_bus = deps.event_bus
        self.config = deps.config
        self.shutdown_event = deps.shutdown_event
        self.http_client = deps.http_client
        self.storage_manager = deps.storage_manager
        self.task_registry = deps.task_registry
        runtime_components = build_rag_runtime_components(deps)
        self.storage: MCPStorageProtocol = runtime_components.storage
        self.mcp_search = deps.mcp_search
        self.worker = runtime_components.worker
        self.metrics = deps.metrics_manager
        self.conv_id_resolution_cache: dict[tuple[int, str], tuple[str, float]] = {}
        self.embedding_availability_cache: dict[str, tuple[bool, float]] = {}
        self.auto_embedding_cache: tuple[str, float] | None = None
        self.cache_max_size = 1000
        self.cache_ttl_sec = 300

    async def resolve_conv_id_for_user(self, conv_id: str, user_id: int) -> str:
        return await conversation.resolve_conv_id_for_user(self, conv_id, user_id)

    async def upload_document(
        self,
        conv_id: str,
        user_id: int,
        filename: str,
        content_base64: str,
        file_type: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        embedding_model: str | None = None,
        chunking_strategy: str = "token_based",
        knowledge_attachment_id: str | None = None,
        knowledge_item_index: int | None = None,
        knowledge_source_type: str | None = None,
        knowledge_operation_type: str | None = None,
        client_batch_id: str | None = None,
    ) -> JSONDict:
        return await upload_document(
            self,
            conv_id,
            user_id,
            filename,
            content_base64,
            file_type,
            chunk_size,
            chunk_overlap,
            embedding_model,
            chunking_strategy,
            knowledge_attachment_id,
            knowledge_item_index,
            knowledge_source_type,
            knowledge_operation_type,
            client_batch_id,
        )

    async def upload_document_from_path(
        self,
        conv_id: str,
        user_id: int,
        source_path: str,
        filename: str,
        file_type: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        embedding_model: str | None = None,
        chunking_strategy: str = "token_based",
        existing_task_id: str | None = None,
        transfer_progress_start: int = 0,
        transfer_progress_end: int = 9,
        knowledge_attachment_id: str | None = None,
        knowledge_item_index: int | None = None,
        knowledge_source_type: str | None = None,
        knowledge_operation_type: str | None = None,
        client_batch_id: str | None = None,
    ) -> JSONDict:
        return await upload_document_from_path(
            self,
            conv_id,
            user_id,
            source_path,
            filename,
            file_type,
            chunk_size,
            chunk_overlap,
            embedding_model,
            chunking_strategy,
            existing_task_id,
            transfer_progress_start,
            transfer_progress_end,
            knowledge_attachment_id,
            knowledge_item_index,
            knowledge_source_type,
            knowledge_operation_type,
            client_batch_id,
        )

    async def web_fetch_ingest(
        self,
        conv_id: str,
        user_id: int,
        url: str,
        focus_query: str,
        retrieval_strategy: str,
        top_k: int,
        similarity_threshold: float,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        embedding_model_id: str | None = None,
        chunking_strategy: str = "token_based",
        return_extract_mode: str = "markdown",
        return_max_chars: int = 50_000,
    ) -> JSONDict:
        return await web_fetch_ingest(
            self,
            conv_id,
            user_id,
            url,
            focus_query,
            retrieval_strategy,
            top_k,
            similarity_threshold,
            chunk_size,
            chunk_overlap,
            embedding_model_id,
            chunking_strategy,
            return_extract_mode,
            return_max_chars,
        )

    async def search(
        self,
        conv_id: str,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
        retrieval_strategy: str = "similarity",
        user_id: int = 0,
    ) -> JSONDict:
        return await search_ops.search(
            self,
            conv_id,
            query,
            top_k,
            similarity_threshold,
            retrieval_strategy,
            user_id,
        )

    async def hybrid_search(
        self,
        conv_id: str,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.2,
        bm25_weight: float = 0.3,
        semantic_weight: float = 0.7,
        user_id: int = 0,
        document_id: str | None = None,
        _from_search: bool = False,
        _query_embedding: list[float] | None = None,
    ) -> JSONDict:
        return await hybrid_search.hybrid_search(
            self,
            conv_id,
            query,
            top_k,
            similarity_threshold,
            bm25_weight,
            semantic_weight,
            user_id,
            document_id,
            _from_search,
            _query_embedding,
        )

    async def delete_document(self, conv_id: str, document_id: str) -> bool:
        return await deletion.delete_document(self, conv_id, document_id)

    async def delete_all_documents(self, conv_id: str) -> int:
        return await deletion.delete_all_documents(self, conv_id)

    async def reindex_conversation(self, conv_id: str, user_id: int, model_id: str) -> JSONDict:
        return await reindexing.reindex_conversation(self, conv_id, user_id, model_id)

    async def get_collection_metadata(self, conv_id: str) -> JSONDict:
        return await reindexing.get_collection_metadata(self, conv_id)

    async def rebuild_sparse_index(self, conv_id: str) -> None:
        await reindexing.rebuild_sparse_index(self, conv_id)

    async def initialize(self) -> None:
        logger = get_logger(LOGGER_NAME)
        logger.debug("Initializing RAG Engine...")
        await self.storage.chroma.start()
        self.worker.init_parsers()
        self.worker.start_workers()
        logger.debug("RAG Engine initialized with %s workers", self.worker.worker_count)

    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        logger.debug("Shutting down RAG Engine...")
        self.shutdown_event.set()
        await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
        await self.worker.stop_workers()
        await self.storage.chroma.shutdown()
        logger.debug("RAG Engine shut down")

    async def validate_and_resolve_embedding_model(self, model_id: str) -> tuple[str, int]:
        return await validate_requested_embedding_model(self, model_id)

    async def is_embedding_model_available(self, model_id: str) -> bool:
        return await is_embedding_model_available_with_cache(self, model_id)

    async def ensure_any_embedding_model_available(self) -> str:
        return await ensure_any_embedding_model_available_with_cache(self)
