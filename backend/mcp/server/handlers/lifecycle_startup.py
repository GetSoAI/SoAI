"""SoAI - MCP server lifecycle startup helpers [backend/mcp/server/handlers/lifecycle_startup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.mcp.schema import get_rag_uri_patterns
from mcp.rag.dependencies import MCPRAGDependencies
from mcp.rag.service import MCPRAG

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from mcp.server.handlers.lifecycle_dependencies import (
        MCPLifecycleManagerDependencies,
    )

__all__ = (
    "activate_server_mode_and_initialize_rag",
    "setup_mcp_rag_state",
)


def setup_mcp_rag_state(deps: MCPLifecycleManagerDependencies) -> None:
    if not deps.rag_enabled or deps.http_client is None:
        return
    if deps.mcp_search is None:
        raise StateError("MCPSearch is required for MCP RAG operations.")
    rag_dependencies = MCPRAGDependencies(
        database_files=deps.database_files,
        database_conversation_knowledge_attachments=(
            deps.database_conversation_knowledge_attachments
        ),
        database_knowledge_prompt_state=deps.database_knowledge_prompt_state,
        database_users=deps.database_users,
        database_conversations=deps.database_conversations,
        event_bus=deps.event_bus,
        config=deps.config,
        storage_manager=deps.storage_manager,
        shutdown_event=deps.state.shutdown_event,
        http_client=deps.http_client,
        chroma_path=deps.rag_chroma_path,
        task_registry=deps.task_registry,
        cancellation_history=deps.cancellation_history,
        cancellation_event_bus=deps.cancellation_event_bus,
        token_collection=deps.token_collection,
        cancellation_binder=deps.cancellation_binder,
        finalizer_tracker=deps.finalizer_tracker,
        metrics_manager=deps.metrics_manager,
        processing_workers=deps.rag_processing_workers,
        embedding_timeout=deps.rag_embedding_timeout,
        mcp_search=deps.mcp_search,
        model_resolution_service=deps.model_resolution_service,
        model_information_service=deps.model_information_service,
        parser_registry_factory=deps.parser_registry_factory,
        chunker=deps.rag_chunker,
        managed_ipc_worker_builder=deps.managed_ipc_worker_builder,
        worker_builder=deps.worker_builder,
    )
    deps.state.mcp_rag = MCPRAG(rag_dependencies)
    deps.state.rag_resource_patterns = get_rag_uri_patterns()


async def activate_server_mode_and_initialize_rag(
    deps: MCPLifecycleManagerDependencies,
    *,
    logger: LoggerProtocol,
) -> bool:
    rag_initialized = False
    if deps.server_mode_enabled:
        missing_allowlists: list[str] = []
        if deps.exposed_tools is None:
            missing_allowlists.append("TOOLS.MCP.SERVER_MODE.EXPOSED_TOOLS")
        if deps.exposed_resources is None:
            missing_allowlists.append("TOOLS.MCP.SERVER_MODE.EXPOSED_RESOURCES")
        if deps.exposed_prompts is None:
            missing_allowlists.append("TOOLS.MCP.SERVER_MODE.EXPOSED_PROMPTS")
        if missing_allowlists:
            logger.critical(
                "MCP Server Mode exposure allowlists are not configured. Refusing activation. Missing: %s",
                ", ".join(missing_allowlists),
            )
        else:
            deps.register_tools()
            deps.register_resources()
            deps.register_prompts()
            deps.state.server_mode_active = True
            if deps.state.mcp_rag:
                await deps.state.mcp_rag.initialize()
                logger.debug("RAG Engine initialized successfully")
                rag_initialized = True
            logger.info(
                "MCP Server Mode activated with %d tools, %d resources, and %d prompts.",
                len(deps.state.registration.registered_tools),
                len(deps.state.registration.registered_resources),
                len(deps.state.registration.registered_prompts),
            )
    if deps.state.mcp_rag and not rag_initialized:
        await deps.state.mcp_rag.initialize()
        logger.debug("RAG Engine initialized successfully")
    return bool(deps.state.server_mode_active)
