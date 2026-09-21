"""SoAI - MCP RAG dependencies [backend/mcp/rag/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.di.validation import require_dependencies
from mcp.shared.worker_dependencies_base import MCPWorkerCoreDependencies

if TYPE_CHECKING:
    import httpx2

    from core.conversations.protocols_database_conversation_records import (
        DatabaseConversationsProtocol,
    )
    from core.ipc.managed_worker import ManagedIpcWorkerDependencies
    from core.ipc.protocols import ManagedIpcWorkerProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from mcp.worker.dependencies import MCPWorkerDependencies
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("MCPRAGDependencies",)


@dataclass(frozen=True, slots=True)
class MCPRAGDependencies(MCPWorkerCoreDependencies):
    database_conversations: DatabaseConversationsProtocol
    http_client: httpx2.AsyncClient
    chroma_path: str
    embedding_timeout: int
    model_resolution_service: ModelResolutionServiceProtocol | None
    model_information_service: ModelInformationServiceProtocol | None
    managed_ipc_worker_builder: Callable[[ManagedIpcWorkerDependencies], ManagedIpcWorkerProtocol]
    worker_builder: Callable[[MCPWorkerDependencies], MCPWorkerProtocol]

    @override
    def __post_init__(self) -> None:
        MCPWorkerCoreDependencies.__post_init__(self)
        require_dependencies(
            owner="MCPRAGDependencies",
            chroma_path=self.chroma_path,
            database_conversations=self.database_conversations,
            embedding_timeout=self.embedding_timeout,
            http_client=self.http_client,
            managed_ipc_worker_builder=self.managed_ipc_worker_builder,
            worker_builder=self.worker_builder,
        )
