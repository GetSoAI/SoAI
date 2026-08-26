"""SoAI - MCP storage service [backend/mcp/storage/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.locks import AsyncRWLock, WeakAsyncLRUCache
from core.files.path_resolver import ConfigFilesPathResolver
from core.files.protocols import FilesPathResolverProtocol
from mcp.storage.chroma_ipc_gateway import ChromaIpcGateway
from mcp.storage.dependencies import MCPStorageDependencies
from mcp.storage.internal_protocols import ChromaGatewayProtocol

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("MCPStorage",)


class MCPStorage:

    def __init__(self, deps: MCPStorageDependencies) -> None:
        self._deps = deps
        self.database_files = deps.database_files
        self.event_bus = deps.event_bus
        self.config = deps.config
        self.chroma_path = deps.chroma_path
        self.task_registry: TaskRegistryProtocol = deps.task_registry
        self.embedding_timeout = deps.embedding_timeout
        self.model_resolution_service = deps.model_resolution_service
        self.model_information_service = deps.model_information_service
        self.metrics = deps.metrics_manager
        self.storage_manager = deps.storage_manager
        self.files: FilesPathResolverProtocol = ConfigFilesPathResolver(deps.config)
        self.chroma: ChromaGatewayProtocol = ChromaIpcGateway(
            config=deps.config,
            shutdown_event=deps.shutdown_event,
            database_files=deps.database_files,
            chroma_path=deps.chroma_path,
            managed_ipc_worker_builder=deps.managed_ipc_worker_builder,
            storage_manager=deps.storage_manager,
        )
        self._sparse_index_lock_cache: WeakAsyncLRUCache[asyncio.Lock] = WeakAsyncLRUCache(
            max_size=1000,
        )
        self._chroma_rw_lock_cache: WeakAsyncLRUCache[AsyncRWLock] = WeakAsyncLRUCache(
            max_size=1000,
        )

    async def get_sparse_index_lock(self, conv_id: str) -> asyncio.Lock:
        return await self._sparse_index_lock_cache.get_or_create(conv_id, asyncio.Lock)

    async def get_chroma_rw_lock(self, conv_id: str) -> AsyncRWLock:
        normalized_conv_id = str(conv_id or "").strip()
        return await self._chroma_rw_lock_cache.get_or_create(normalized_conv_id, AsyncRWLock)
