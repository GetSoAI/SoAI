"""SoAI - Shared MCP worker dependency bundle base [backend/mcp/shared/worker_dependencies_base.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.files.protocols import FileParserProtocol
from core.mcp.protocols_main import MCPSearchProtocol

if TYPE_CHECKING:
    from core.attachments.protocols_database import (
        DatabaseConversationKnowledgeAttachmentsProtocol,
    )
    from core.config.protocols import ConfigProtocol
    from core.events.protocols import EventBusProtocol
    from core.files.protocols import DatabaseFilesProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.rag.protocols import DatabaseKnowledgePromptStateProtocol
    from core.tasks.protocols import (
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
        TokenCollectionProtocol,
    )
    from core.users.protocols_database import DatabaseUsersProtocol
    from mcp.rag.indexing.chunking import DocumentChunker

__all__ = ("MCPWorkerCoreDependencies",)


@dataclass(frozen=True, slots=True)
class MCPWorkerCoreDependencies:
    database_users: DatabaseUsersProtocol
    database_files: DatabaseFilesProtocol
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    event_bus: EventBusProtocol
    config: ConfigProtocol
    storage_manager: StorageManagerProtocol
    shutdown_event: asyncio.Event
    task_registry: TaskRegistryProtocol
    mcp_search: MCPSearchProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    metrics_manager: MetricsManagerProtocol
    processing_workers: int
    parser_registry_factory: Callable[[], dict[str, FileParserProtocol]]
    chunker: DocumentChunker

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPWorkerCoreDependencies",
            cancellation_binder=self.cancellation_binder,
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            chunker=self.chunker,
            config=self.config,
            database_conversation_knowledge_attachments=(
                self.database_conversation_knowledge_attachments
            ),
            database_users=self.database_users,
            database_files=self.database_files,
            database_knowledge_prompt_state=self.database_knowledge_prompt_state,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            mcp_search=self.mcp_search,
            metrics_manager=self.metrics_manager,
            parser_registry_factory=self.parser_registry_factory,
            processing_workers=self.processing_workers,
            shutdown_event=self.shutdown_event,
            storage_manager=self.storage_manager,
            task_registry=self.task_registry,
            token_collection=self.token_collection,
        )
