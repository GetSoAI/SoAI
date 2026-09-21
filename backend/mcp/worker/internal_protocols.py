"""SoAI - MCP worker internal protocols [backend/mcp/worker/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from core.files.protocols import FileParserProtocol

if TYPE_CHECKING:
    import asyncio

    from core.attachments.protocols_database import (
        DatabaseConversationKnowledgeAttachmentsProtocol,
    )
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.config.protocols import ConfigProtocol
    from core.events.protocols import EventBusProtocol
    from core.files.protocols import DatabaseFilesProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.mcp.protocols_main import MCPSearchProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.rag.job_operations import (
        RAGDocumentStatusJobUpdateRequest,
        RAGDocumentStatusUpdateRequest,
    )
    from core.rag.protocols import DatabaseKnowledgePromptStateProtocol
    from core.tasks.protocols import (
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TaskRegistryProtocol,
        TokenCollectionProtocol,
    )
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from core.users.protocols_database import DatabaseUsersProtocol
    from mcp.rag.indexing.chunking import DocumentChunker
    from mcp.storage.internal_protocols import MCPStorageProtocol
    from mcp.worker.reindex_lock_registry import ReindexLockRegistry

__all__ = ("MCPWorkerProtocol",)


@runtime_checkable
class MCPWorkerProtocol(Protocol):

    config: ConfigProtocol
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    database_users: DatabaseUsersProtocol
    database_files: DatabaseFilesProtocol
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    event_bus: EventBusProtocol
    mcp_search: MCPSearchProtocol
    shutdown_event: asyncio.Event
    storage: MCPStorageProtocol
    storage_manager: StorageManagerProtocol
    parsers: dict[str, FileParserProtocol]
    chunker: DocumentChunker
    processing_queue: asyncio.Queue[JSONDict]
    processing_workers: list[asyncio.Task[None]]
    worker_count: int
    metrics: MetricsManagerProtocol
    reindex_locks: ReindexLockRegistry

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def cancellation_history(self) -> CancellationHistoryProtocol: ...

    @property
    def cancellation_event_bus(self) -> CancellationEventBusProtocol: ...

    @property
    def token_collection(self) -> TokenCollectionProtocol: ...

    async def update_rag_document_status(
        self,
        request: RAGDocumentStatusUpdateRequest,
    ) -> None: ...

    async def update_rag_document_status_for_job(
        self,
        request: RAGDocumentStatusJobUpdateRequest,
    ) -> None: ...

    async def finalize_knowledge_attachment_task(
        self,
        *,
        task_id: str,
        processing_state: str,
        terminal_item_status: str,
        error_message: str | None,
    ) -> None: ...

    def init_parsers(self) -> None: ...

    def start_workers(self) -> None: ...

    async def stop_workers(self) -> None: ...

    async def complete_task(
        self,
        task_id: str,
        result: JSONDict | None = None,
        message: str = "Operation completed",
    ) -> Task | None: ...

    async def fail_task(self, task_id: str, error_message: str) -> None: ...

    async def cancel_task(self, task_id: str, reason: str) -> None: ...

    async def send_progress(
        self,
        task_id: str,
        percent: int,
        message: str,
        details: str = "",
    ) -> None: ...

    async def check_cancellation(
        self,
        task_id: str,
        operation: str,
        token: CancellationTokenProtocol | None = None,
    ) -> None: ...
