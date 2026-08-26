"""SoAI - MCP server runtime assembly [backend/app/composition/build_mcp_server_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.browser_adblock.service import (
    EasyListAdblockService,
    build_easylist_adblock_service_dependencies,
)
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.mcp.protocol_versions import MCP_PROTOCOL_VERSION
from core.tasks.service_lifecycle import initialize_managed_task_group
from core.timing.monotonic import monotonic_ms
from mcp.server.component_factory import ComponentFactoryInputs
from mcp.server.constants import DEFAULT_PAGE_SIZE
from mcp.server.dependencies import MCPServerDependencies
from mcp.server.initialization import create_mcp_server_intermediate_services
from mcp.server.runtime_bundle import MCPServerRuntimeBundle

if TYPE_CHECKING:
    from core.timing.startup_timings import StartupTimingsRecorder
    from mcp.server.service import MCPServer

__all__ = ("build_mcp_server_runtime_bundle",)

LOGGER_NAME = "SoAI.app.composition.build_mcp_server_runtime"


def build_mcp_server_runtime_bundle(
    *,
    server: MCPServer,
    dependencies: MCPServerDependencies,
    startup_timings: StartupTimingsRecorder,
) -> MCPServerRuntimeBundle:
    logger = get_logger(LOGGER_NAME)
    step_started_ms = monotonic_ms()
    (
        lifecycle,
        shutdown_event,
        cancellation_binder,
        finalizer_tracker,
        background_tasks,
    ) = initialize_managed_task_group(
        "mcp server tasks",
        logger=logger,
        error_message="MCP manager lifecycle did not initialize a managed task group.",
        cancellation_binder=dependencies.cancellation_binder,
        finalizer_tracker=dependencies.finalizer_tracker,
        operation_name="mcp.server.background_task_completion",
    )
    startup_timings.record_since_ms("assembly.mcp.lifecycle_group_ms", step_started_ms)
    http_client = dependencies.http_client
    if http_client is None:
        raise StateError("HTTP client is required for MCP server runtime assembly.")
    step_started_ms = monotonic_ms()
    adblock_service = EasyListAdblockService(
        build_easylist_adblock_service_dependencies(
            config=dependencies.config,
            http_client=http_client,
            logger=logger,
            storage_manager=dependencies.storage_manager,
        ),
    )
    startup_timings.record_since_ms("assembly.mcp.adblock_service_ms", step_started_ms)
    step_started_ms = monotonic_ms()
    intermediate_services = create_mcp_server_intermediate_services(
        dependencies,
        shutdown_event,
        background_tasks,
        adblock_service=adblock_service,
        startup_timings=startup_timings,
    )
    startup_timings.record_since_ms("assembly.mcp.intermediate_services_ms", step_started_ms)
    runtime_config = intermediate_services.runtime_config
    step_started_ms = monotonic_ms()
    components = dependencies.server_components_builder(
        ComponentFactoryInputs(
            state=intermediate_services.state,
            active_client_context=dependencies.active_client_context,
            active_task_context=dependencies.active_task_context,
            active_user_id_context=dependencies.active_user_id_context,
            event_bus=dependencies.event_bus,
            config=dependencies.config,
            database_files=dependencies.database_files,
            database_conversation_knowledge_attachments=(
                dependencies.database_conversation_knowledge_attachments
            ),
            database_knowledge_prompt_state=dependencies.database_knowledge_prompt_state,
            database_users=dependencies.database_users,
            database_conversations=dependencies.database_conversations,
            storage_manager=dependencies.storage_manager,
            task_registry=dependencies.task_registry,
            task_registry_queries=dependencies.task_registry_queries,
            cancellation_history=dependencies.cancellation_history,
            cancellation_event_bus=dependencies.cancellation_event_bus,
            token_collection=dependencies.token_collection,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            metrics_manager=dependencies.metrics_manager,
            model_resolution_service=dependencies.model_resolution_service,
            model_information_service=dependencies.model_information_service,
            http_client=dependencies.http_client,
            web_fetcher=intermediate_services.web_fetcher,
            mcp_search=intermediate_services.mcp_search,
            mcp_remote=dependencies.mcp_remote,
            utility_tools=intermediate_services.utility_tools,
            background_tasks=background_tasks,
            exposed_tools=runtime_config.exposed_tools,
            exposed_resources=runtime_config.exposed_resources,
            exposed_prompts=runtime_config.exposed_prompts,
            protocol_version=MCP_PROTOCOL_VERSION,
            default_page_size=DEFAULT_PAGE_SIZE,
            session_ttl_sec=runtime_config.session_ttl_sec,
            client_notification_queue_size=runtime_config.client_notification_queue_size,
            client_sse_replay_buffer_size=runtime_config.client_sse_replay_buffer_size,
            host_mode_enabled=runtime_config.host_mode_enabled,
            enabled=runtime_config.enabled,
            server_mode_enabled=runtime_config.server_mode_enabled,
            tasks_enabled=runtime_config.tasks_enabled,
            tasks_default_ttl_sec=runtime_config.tasks_default_ttl_sec,
            user_interaction_timeout_ms=runtime_config.user_interaction_timeout_ms,
            tasks_max_concurrent_per_client=runtime_config.tasks_max_concurrent_per_client,
            rag_enabled=runtime_config.rag_enabled,
            rag_chroma_path=runtime_config.rag_chroma_path or "",
            rag_processing_workers=runtime_config.rag_processing_workers,
            rag_embedding_timeout=runtime_config.rag_embedding_timeout,
            session_sweep_interval_sec=runtime_config.session_sweep_interval_sec,
            parser_registry_factory=dependencies.parser_registry_factory,
            track_background_task=server.track_background_task,
            server_ref=server,
        ),
        intermediate_services.mcp_search_api_keys.load_search_api_keys_from_persistence,
    )
    startup_timings.record_since_ms("assembly.mcp.components_ms", step_started_ms)
    return MCPServerRuntimeBundle(
        lifecycle=lifecycle,
        shutdown_event=shutdown_event,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        background_tasks=background_tasks,
        web_fetcher=intermediate_services.web_fetcher,
        state=intermediate_services.state,
        search=intermediate_services.mcp_search,
        search_api_keys=intermediate_services.mcp_search_api_keys,
        utility_tools=intermediate_services.utility_tools,
        runtime_config=runtime_config,
        components=components,
    )
