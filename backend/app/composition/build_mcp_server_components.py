"""SoAI - MCP server components assembly [backend/app/composition/build_mcp_server_components.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Coroutine

from core.concurrency.bounded_blocking import (
    BoundedThreadPoolConfig,
    create_bounded_thread_pool_from_env,
)
from core.ipc.managed_worker import ManagedIpcWorker
from core.logging.trace import get_logger
from mcp.rag.indexing.chunking import DocumentChunker
from mcp.server.component_factory import ComponentFactoryInputs, MCPServerComponents
from mcp.server.handlers.context_manager import (
    MCPContextManager,
    MCPContextManagerDependencies,
)
from mcp.server.handlers.host_mode_client import (
    MCPHostModeClient,
    MCPHostModeClientDependencies,
)
from mcp.server.handlers.lifecycle_dependencies import MCPLifecycleManagerDependencies
from mcp.server.handlers.lifecycle_manager import MCPLifecycleManager
from mcp.server.handlers.notification_service import (
    MCPNotificationService,
    MCPNotificationServiceDependencies,
)
from mcp.server.handlers.pagination_codec import (
    MCPPaginationCodec,
    MCPPaginationCodecDependencies,
)
from mcp.server.handlers.registration_service import (
    MCPRegistrationService,
    MCPRegistrationServiceDependencies,
)
from mcp.server.handlers.session_manager import (
    MCPSessionManager,
    MCPSessionManagerDependencies,
)
from mcp.server.handlers.streaming_service import (
    MCPStreamingService,
    MCPStreamingServiceDependencies,
)
from mcp.server.handlers.task_service import MCPTaskService, MCPTaskServiceDependencies
from mcp.tools.shell_session_support import cleanup_pruned_shell_sessions
from mcp.worker.service import MCPWorker

__all__ = ("build_mcp_server_components",)

LOGGER_NAME = "SoAI.app.composition.build_mcp_server_components"


def build_mcp_server_components(
    inputs: ComponentFactoryInputs,
    load_search_api_keys: Callable[[], Coroutine[None, None, None]],
) -> MCPServerComponents:
    logger = get_logger(LOGGER_NAME)
    session_manager = MCPSessionManager(
        MCPSessionManagerDependencies(
            state=inputs.state,
            session_ttl_sec=inputs.session_ttl_sec,
            cleanup_pruned_shell_sessions=lambda: cleanup_pruned_shell_sessions(
                inputs.utility_tools,
                logger=logger,
                operation="mcp.server.session_manager.cleanup_pruned_shell_sessions",
            ),
        ),
    )
    streaming_service = MCPStreamingService(
        MCPStreamingServiceDependencies(
            state=inputs.state,
            notification_queue_size=inputs.client_notification_queue_size,
            sse_replay_buffer_size=inputs.client_sse_replay_buffer_size,
            metrics_manager=inputs.metrics_manager,
            close_client_session=session_manager.close_client_session,
        ),
    )
    notification_service = MCPNotificationService(
        MCPNotificationServiceDependencies(
            state=inputs.state,
            event_bus=inputs.event_bus,
            resolve_session_id=session_manager.resolve_session_id,
            emit_client_stream_message=streaming_service.emit_client_stream_message,
            try_emit_client_stream_message=streaming_service.try_emit_client_stream_message,
            metrics_manager=inputs.metrics_manager,
        ),
    )
    pagination_codec = MCPPaginationCodec(
        MCPPaginationCodecDependencies(
            default_page_size=inputs.default_page_size,
        ),
    )
    context_manager = MCPContextManager(
        MCPContextManagerDependencies(
            state=inputs.state,
            database_conversations=inputs.database_conversations,
            database_files=inputs.database_files,
            active_client_context=inputs.active_client_context,
            active_task_context=inputs.active_task_context,
            active_user_id_context=inputs.active_user_id_context,
            get_session=session_manager.get_session,
            get_session_user_id=session_manager.get_session_user_id,
            resolve_session_id=session_manager.resolve_session_id,
        ),
    )
    host_mode_client = MCPHostModeClient(
        MCPHostModeClientDependencies(
            state=inputs.state,
            mcp_remote=inputs.mcp_remote,
            background_tasks=inputs.background_tasks,
            protocol_version=inputs.protocol_version,
            host_mode_enabled=inputs.host_mode_enabled,
        ),
    )
    registration_service = MCPRegistrationService(
        MCPRegistrationServiceDependencies(
            state=inputs.state,
            exposed_tools=inputs.exposed_tools,
            exposed_resources=inputs.exposed_resources,
            exposed_prompts=inputs.exposed_prompts,
            model_information_service=inputs.model_information_service,
            mcp_search=inputs.mcp_search,
            utility_tools=inputs.utility_tools,
            require_authenticated_user_id=context_manager.require_authenticated_user_id,
            current_session_identity=context_manager.current_session_identity,
            server_ref=inputs.server_ref,
        ),
    )
    task_service = MCPTaskService(
        MCPTaskServiceDependencies(
            state=inputs.state,
            task_registry=inputs.task_registry,
            task_registry_queries=inputs.task_registry_queries,
            tasks_default_ttl_ms=int(inputs.tasks_default_ttl_sec) * 1000,
            user_interaction_timeout_ms=inputs.user_interaction_timeout_ms,
            get_session=session_manager.get_session,
            resolve_session_id=session_manager.resolve_session_id,
            has_client_session=session_manager.has_client_session,
            ensure_client_session=session_manager.ensure_client_session,
            emit_client_stream_message=streaming_service.emit_client_stream_message,
            metrics_manager=inputs.metrics_manager,
            server_ref=inputs.server_ref,
        ),
    )
    rag_chunker = DocumentChunker(
        create_bounded_thread_pool_from_env(
            BoundedThreadPoolConfig(
                label="rag-chunking",
                thread_name_prefix="soai-rag-chunk",
                max_workers_env="SOAI_RAG_CHUNKING_MAX_WORKERS",
                max_in_flight_env="SOAI_RAG_CHUNKING_MAX_IN_FLIGHT",
                default_max_workers=1,
                minimum_workers=1,
                maximum_workers=4,
                default_in_flight_multiplier=2,
                default_min_in_flight=2,
                max_in_flight_limit=16,
            ),
        ),
    )
    lifecycle_manager = MCPLifecycleManager(
        MCPLifecycleManagerDependencies(
            state=inputs.state,
            config=inputs.config,
            event_bus=inputs.event_bus,
            enabled=inputs.enabled,
            server_mode_enabled=inputs.server_mode_enabled,
            tasks_enabled=inputs.tasks_enabled,
            rag_enabled=inputs.rag_enabled,
            database_files=inputs.database_files,
            database_conversation_knowledge_attachments=(
                inputs.database_conversation_knowledge_attachments
            ),
            database_knowledge_prompt_state=inputs.database_knowledge_prompt_state,
            database_users=inputs.database_users,
            database_conversations=inputs.database_conversations,
            storage_manager=inputs.storage_manager,
            task_registry=inputs.task_registry,
            task_registry_queries=inputs.task_registry_queries,
            rag_chroma_path=inputs.rag_chroma_path,
            rag_processing_workers=inputs.rag_processing_workers,
            rag_embedding_timeout=inputs.rag_embedding_timeout,
            cancellation_history=inputs.cancellation_history,
            cancellation_event_bus=inputs.cancellation_event_bus,
            token_collection=inputs.token_collection,
            cancellation_binder=inputs.cancellation_binder,
            finalizer_tracker=inputs.finalizer_tracker,
            tasks_default_ttl_sec=inputs.tasks_default_ttl_sec,
            tasks_max_concurrent_per_client=inputs.tasks_max_concurrent_per_client,
            user_interaction_timeout_ms=inputs.user_interaction_timeout_ms,
            metrics_manager=inputs.metrics_manager,
            model_resolution_service=inputs.model_resolution_service,
            model_information_service=inputs.model_information_service,
            session_sweep_interval_sec=inputs.session_sweep_interval_sec,
            http_client=inputs.http_client,
            web_fetcher=inputs.web_fetcher,
            mcp_search=inputs.mcp_search,
            background_tasks=inputs.background_tasks,
            parser_registry_factory=inputs.parser_registry_factory,
            rag_chunker=rag_chunker,
            mcp_remote=inputs.mcp_remote,
            server_ref=inputs.server_ref,
            managed_ipc_worker_builder=ManagedIpcWorker,
            worker_builder=MCPWorker,
            load_search_api_keys=load_search_api_keys,
            register_tools=registration_service.register_soai_tools,
            register_local_tools=registration_service.register_local_tools,
            register_resources=registration_service.register_soai_resources,
            register_prompts=registration_service.register_soai_prompts,
            exposed_tools=inputs.exposed_tools,
            exposed_resources=inputs.exposed_resources,
            exposed_prompts=inputs.exposed_prompts,
            session_cleanup_loop=session_manager.session_cleanup_loop,
            track_background_task=inputs.track_background_task,
            close_all_sessions=session_manager.close_all_client_sessions,
        ),
    )
    return MCPServerComponents(
        session=session_manager,
        streaming=streaming_service,
        notification=notification_service,
        pagination=pagination_codec,
        context=context_manager,
        host_mode=host_mode_client,
        registration=registration_service,
        task=task_service,
        lifecycle=lifecycle_manager,
    )
