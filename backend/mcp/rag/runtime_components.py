"""SoAI - MCP RAG runtime component assembly [backend/mcp/rag/runtime_components.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.storage.dependencies import MCPStorageDependencies
from mcp.storage.service import MCPStorage
from mcp.worker.dependencies import MCPWorkerDependencies

if TYPE_CHECKING:
    from mcp.rag.dependencies import MCPRAGDependencies
    from mcp.storage.internal_protocols import MCPStorageProtocol
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("MCPRAGRuntimeComponents", "build_rag_runtime_components")


@dataclass(frozen=True, slots=True)
class MCPRAGRuntimeComponents:
    storage: MCPStorageProtocol
    worker: MCPWorkerProtocol


def build_rag_runtime_components(deps: MCPRAGDependencies) -> MCPRAGRuntimeComponents:
    storage_dependencies = MCPStorageDependencies(
        database_files=deps.database_files,
        event_bus=deps.event_bus,
        config=deps.config,
        shutdown_event=deps.shutdown_event,
        chroma_path=deps.chroma_path,
        managed_ipc_worker_builder=deps.managed_ipc_worker_builder,
        storage_manager=deps.storage_manager,
        task_registry=deps.task_registry,
        metrics_manager=deps.metrics_manager,
        embedding_timeout=deps.embedding_timeout,
        model_resolution_service=deps.model_resolution_service,
        model_information_service=deps.model_information_service,
    )
    storage: MCPStorageProtocol = MCPStorage(storage_dependencies)
    worker_dependencies = MCPWorkerDependencies(
        database_files=deps.database_files,
        database_conversation_knowledge_attachments=(
            deps.database_conversation_knowledge_attachments
        ),
        database_knowledge_prompt_state=deps.database_knowledge_prompt_state,
        event_bus=deps.event_bus,
        config=deps.config,
        storage_manager=deps.storage_manager,
        shutdown_event=deps.shutdown_event,
        task_registry=deps.task_registry,
        storage=storage,
        mcp_search=deps.mcp_search,
        cancellation_history=deps.cancellation_history,
        cancellation_event_bus=deps.cancellation_event_bus,
        token_collection=deps.token_collection,
        cancellation_binder=deps.cancellation_binder,
        finalizer_tracker=deps.finalizer_tracker,
        metrics_manager=deps.metrics_manager,
        processing_workers=deps.processing_workers,
        parser_registry_factory=deps.parser_registry_factory,
        chunker=deps.chunker,
    )
    return MCPRAGRuntimeComponents(
        storage=storage,
        worker=deps.worker_builder(worker_dependencies),
    )
