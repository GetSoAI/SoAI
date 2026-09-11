"""SoAI - MCP server lifecycle dependency bundle [backend/mcp/server/handlers/lifecycle_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.attachments.protocols_database import (
        DatabaseConversationKnowledgeAttachmentsProtocol,
    )
    from core.concurrency.task_groups import ManagedTaskGroup
    from core.config.protocols import ConfigProtocol
    from core.conversations.protocols_database_conversation_records import (
        DatabaseConversationsProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.files.protocols import DatabaseFilesProtocol, FileParserProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.ipc.managed_worker import ManagedIpcWorkerDependencies
    from core.ipc.protocols import ManagedIpcWorkerProtocol
    from core.mcp.protocols_main import MCPSearchProtocol
    from core.mcp.protocols_runtime import MCPRemoteHostProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.rag.protocols import DatabaseKnowledgePromptStateProtocol
    from core.tasks.protocols import (
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
        TokenCollectionProtocol,
    )
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.users.protocols_database import DatabaseUsersProtocol
    from mcp.host.internal_protocols import MCPServerHostProtocol
    from mcp.rag.indexing.chunking import DocumentChunker
    from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol
    from mcp.server.state import MCPServerState
    from mcp.worker.dependencies import MCPWorkerDependencies
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("MCPLifecycleManagerDependencies",)


@dataclass(frozen=True, slots=True)
class MCPLifecycleManagerDependencies:
    state: MCPServerState
    config: ConfigProtocol
    event_bus: EventBusProtocol
    enabled: bool
    server_mode_enabled: bool
    tasks_enabled: bool
    rag_enabled: bool
    rag_chroma_path: str
    rag_processing_workers: int
    rag_embedding_timeout: int
    database_files: DatabaseFilesProtocol
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    database_users: DatabaseUsersProtocol
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    task_registry_queries: TaskRegistryQueryView
    database_conversations: DatabaseConversationsProtocol
    task_registry: TaskRegistryProtocol
    storage_manager: StorageManagerProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    tasks_default_ttl_sec: int
    tasks_max_concurrent_per_client: int
    user_interaction_timeout_ms: int
    metrics_manager: MetricsManagerProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    session_sweep_interval_sec: int
    http_client: httpx2.AsyncClient | None
    web_fetcher: WebContentFetcherProtocol | None
    mcp_search: MCPSearchProtocol | None
    background_tasks: ManagedTaskGroup
    parser_registry_factory: Callable[[], dict[str, FileParserProtocol]]
    rag_chunker: DocumentChunker
    managed_ipc_worker_builder: Callable[[ManagedIpcWorkerDependencies], ManagedIpcWorkerProtocol]
    worker_builder: Callable[[MCPWorkerDependencies], MCPWorkerProtocol]
    load_search_api_keys: Callable[[], Awaitable[None]]
    register_tools: Callable[[], None]
    register_local_tools: Callable[[], None]
    register_resources: Callable[[], None]
    register_prompts: Callable[[], None]
    exposed_tools: set[str] | None
    exposed_resources: set[str] | None
    exposed_prompts: set[str] | None
    session_cleanup_loop: Callable[[int], Coroutine[None, None, None]]
    track_background_task: Callable[[asyncio.Task[None]], None]
    close_all_sessions: Callable[[], Awaitable[None]]
    mcp_remote: MCPRemoteHostProtocol
    server_ref: MCPServerHostProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPLifecycleManagerDependencies",
            background_tasks=self.background_tasks,
            cancellation_binder=self.cancellation_binder,
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            close_all_sessions=self.close_all_sessions,
            config=self.config,
            database_conversations=self.database_conversations,
            database_conversation_knowledge_attachments=(
                self.database_conversation_knowledge_attachments
            ),
            database_files=self.database_files,
            database_knowledge_prompt_state=self.database_knowledge_prompt_state,
            database_users=self.database_users,
            enabled=self.enabled,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            load_search_api_keys=self.load_search_api_keys,
            managed_ipc_worker_builder=self.managed_ipc_worker_builder,
            metrics_manager=self.metrics_manager,
            model_information_service=self.model_information_service,
            model_resolution_service=self.model_resolution_service,
            parser_registry_factory=self.parser_registry_factory,
            rag_chroma_path=self.rag_chroma_path,
            rag_chunker=self.rag_chunker,
            rag_embedding_timeout=self.rag_embedding_timeout,
            rag_enabled=self.rag_enabled,
            rag_processing_workers=self.rag_processing_workers,
            register_prompts=self.register_prompts,
            register_resources=self.register_resources,
            register_local_tools=self.register_local_tools,
            register_tools=self.register_tools,
            server_mode_enabled=self.server_mode_enabled,
            session_cleanup_loop=self.session_cleanup_loop,
            session_sweep_interval_sec=self.session_sweep_interval_sec,
            state=self.state,
            storage_manager=self.storage_manager,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
            tasks_default_ttl_sec=self.tasks_default_ttl_sec,
            tasks_enabled=self.tasks_enabled,
            tasks_max_concurrent_per_client=self.tasks_max_concurrent_per_client,
            user_interaction_timeout_ms=self.user_interaction_timeout_ms,
            token_collection=self.token_collection,
            track_background_task=self.track_background_task,
            worker_builder=self.worker_builder,
            mcp_remote=self.mcp_remote,
            server_ref=self.server_ref,
        )
