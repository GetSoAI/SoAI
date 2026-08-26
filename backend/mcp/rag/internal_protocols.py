"""SoAI - MCP RAG internal protocols [backend/mcp/rag/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol, override

from core.mcp.protocols_main import MCPSearchProtocol
from core.mcp.protocols_rag import MCPRAGProtocol
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TaskTypeId

if TYPE_CHECKING:
    import httpx2

    from core.attachments.protocols_database import (
        DatabaseConversationKnowledgeAttachmentsProtocol,
    )
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.config.protocols import ConfigProtocol
    from core.conversations.protocols_database_conversation_records import (
        DatabaseConversationsProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.files.protocols import DatabaseFilesProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.rag.protocols import DatabaseKnowledgePromptStateProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from core.users.protocols_database import DatabaseUsersProtocol
    from mcp.storage.internal_protocols import MCPStorageProtocol
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "CreateRagTaskProtocol",
    "MCPRAGInternalProtocol",
    "MCPRAGSearchContextProtocol",
    "SearchDocumentContextProtocol",
)


class MCPRAGSearchContextProtocol(Protocol):
    database_files: DatabaseFilesProtocol
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    event_bus: EventBusProtocol
    mcp_search: MCPSearchProtocol
    metrics: MetricsManagerProtocol

    @property
    def storage(self) -> MCPStorageProtocol: ...


class MCPRAGInternalProtocol(MCPRAGProtocol, Protocol):
    database_files: DatabaseFilesProtocol
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    database_users: DatabaseUsersProtocol
    database_conversations: DatabaseConversationsProtocol
    event_bus: EventBusProtocol
    config: ConfigProtocol
    shutdown_event: asyncio.Event
    http_client: httpx2.AsyncClient
    storage_manager: StorageManagerProtocol
    mcp_search: MCPSearchProtocol
    metrics: MetricsManagerProtocol

    @property
    @override
    def storage(self) -> MCPStorageProtocol: ...

    @property
    @override
    def worker(self) -> MCPWorkerProtocol: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def conv_id_resolution_cache(self) -> dict[tuple[int, str], tuple[str, float]]: ...

    @property
    def embedding_availability_cache(self) -> dict[str, tuple[bool, float]]: ...

    @property
    def auto_embedding_cache(self) -> tuple[str, float] | None: ...

    @auto_embedding_cache.setter
    def auto_embedding_cache(self, value: tuple[str, float] | None) -> None: ...

    @property
    def cache_max_size(self) -> int: ...

    @property
    def cache_ttl_sec(self) -> int: ...

    async def delete_all_documents(self, conv_id: str) -> int: ...

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
    ) -> JSONDict: ...

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
    ) -> JSONDict: ...

    @override
    async def get_collection_metadata(self, conv_id: str) -> JSONDict: ...

    async def rebuild_sparse_index(self, conv_id: str) -> None: ...


class CreateRagTaskProtocol(Protocol):
    async def __call__(
        self,
        task_registry: TaskRegistryProtocol,
        *,
        task_type: TaskTypeId,
        user_id: int,
        conv_id: str,
        status: TaskStatus,
        progress_total: int,
        metadata: JSONDict | None = None,
    ) -> Task: ...


class SearchDocumentContextProtocol(Protocol):
    async def __call__(
        self,
        worker: MCPWorkerProtocol,
        *,
        conv_id: str,
        document_id: str,
        query: str,
        top_k: int,
        similarity_threshold: float,
        retrieval_strategy: str,
        user_id: int,
        embedding_model: str,
        task_id: str,
        token: CancellationTokenProtocol | None,
    ) -> JSONDict: ...
