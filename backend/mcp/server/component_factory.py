"""SoAI - MCP server component factory [backend/mcp/server/component_factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextvars
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.attachments.protocols_database import (
    DatabaseConversationKnowledgeAttachmentsProtocol,
)
from core.config.protocols import ConfigProtocol
from core.conversations.protocols_database_conversation_records import (
    DatabaseConversationsProtocol,
)
from core.events.protocols import EventBusProtocol
from core.files.protocols import DatabaseFilesProtocol, FileParserProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.mcp.protocols_main import MCPRemoteProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols import (
    ModelInformationServiceProtocol,
    ModelResolutionServiceProtocol,
)
from core.rag.protocols import DatabaseKnowledgePromptStateProtocol
from core.users.protocols_database import DatabaseUsersProtocol
from mcp.host.internal_protocols import MCPServerHostProtocol
from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol

if TYPE_CHECKING:
    import asyncio

    from core.concurrency.task_groups import ManagedTaskGroup
    from core.mcp.protocols_main import MCPSearchProtocol
    from core.tasks.protocols import (
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
        TokenCollectionProtocol,
    )
    from core.tasks.protocols_query import TaskRegistryQueryView
    from mcp.server.handlers.context_manager import MCPContextManager
    from mcp.server.handlers.host_mode_client import MCPHostModeClient
    from mcp.server.handlers.lifecycle_manager import MCPLifecycleManager
    from mcp.server.handlers.notification_service import MCPNotificationService
    from mcp.server.handlers.pagination_codec import MCPPaginationCodec
    from mcp.server.handlers.registration_service import MCPRegistrationService
    from mcp.server.handlers.session_manager import MCPSessionManager
    from mcp.server.handlers.streaming_service import MCPStreamingService
    from mcp.server.handlers.task_service import MCPTaskService
    from mcp.server.state import MCPServerState
    from mcp.tools.service import MCPUtilityTools

__all__ = (
    "ComponentFactoryInputs",
    "MCPServerComponents",
)


@dataclass(frozen=True, slots=True)
class ComponentFactoryInputs:
    state: MCPServerState
    active_client_context: contextvars.ContextVar[str | None]
    active_task_context: contextvars.ContextVar[str | None]
    active_user_id_context: contextvars.ContextVar[int]
    event_bus: EventBusProtocol
    config: ConfigProtocol
    database_files: DatabaseFilesProtocol
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    database_users: DatabaseUsersProtocol
    database_conversations: DatabaseConversationsProtocol
    storage_manager: StorageManagerProtocol
    task_registry: TaskRegistryProtocol
    task_registry_queries: TaskRegistryQueryView
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    token_collection: TokenCollectionProtocol
    metrics_manager: MetricsManagerProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    http_client: httpx2.AsyncClient | None
    web_fetcher: WebContentFetcherProtocol | None
    mcp_search: MCPSearchProtocol | None
    mcp_remote: MCPRemoteProtocol
    utility_tools: MCPUtilityTools
    background_tasks: ManagedTaskGroup
    exposed_tools: set[str] | None
    exposed_resources: set[str] | None
    exposed_prompts: set[str] | None
    protocol_version: str
    default_page_size: int
    session_ttl_sec: int
    client_notification_queue_size: int
    client_sse_replay_buffer_size: int
    host_mode_enabled: bool
    enabled: bool
    server_mode_enabled: bool
    tasks_enabled: bool
    tasks_default_ttl_sec: int
    user_interaction_timeout_ms: int
    tasks_max_concurrent_per_client: int
    rag_enabled: bool
    rag_chroma_path: str
    rag_processing_workers: int
    rag_embedding_timeout: int
    session_sweep_interval_sec: int
    parser_registry_factory: Callable[[], dict[str, FileParserProtocol]]
    track_background_task: Callable[[asyncio.Task[None]], None]
    server_ref: MCPServerHostProtocol


@dataclass(frozen=True, slots=True)
class MCPServerComponents:
    session: MCPSessionManager
    streaming: MCPStreamingService
    notification: MCPNotificationService
    pagination: MCPPaginationCodec
    context: MCPContextManager
    host_mode: MCPHostModeClient
    registration: MCPRegistrationService
    task: MCPTaskService
    lifecycle: MCPLifecycleManager
