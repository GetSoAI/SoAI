"""SoAI - MCP storage internal protocols [backend/mcp/storage/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping, Sequence
from typing import TYPE_CHECKING, Protocol

from core.concurrency.locks import AsyncRWLock, WeakAsyncLRUCache
from core.files.protocols import FilesPathResolverProtocol
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.config.protocols import ConfigProtocol
    from core.events.protocols import EventBusProtocol
    from core.files.protocols import DatabaseFilesProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONValue

__all__ = (
    "ChromaClientOwnerProtocol",
    "ChromaClientProtocol",
    "ChromaCollectionProtocol",
    "ChromaGatewayProtocol",
    "EmbeddingCancellationChecker",
    "EmbeddingProgressCallback",
    "MCPStorageProtocol",
)


class ChromaGatewayProtocol(Protocol):
    async def start(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def ensure_collection(
        self,
        *,
        conv_id: str,
        collection_name: str,
        embedding_model: str,
        effective_model: str,
        timeout_sec: float,
    ) -> None: ...

    async def add_upsert_ids(
        self,
        *,
        conv_id: str,
        collection_name: str,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str],
        metadatas: Sequence[Mapping[str, JSONValue]],
        batch_size: int,
        timeout_sec: float,
        cancel_wait_sec: float,
        token: CancellationTokenProtocol | None,
    ) -> None: ...

    async def query(
        self,
        *,
        conv_id: str,
        collection_name: str,
        query_embeddings: Sequence[Sequence[float]],
        n_results: int,
        where: Mapping[str, JSONValue] | None,
        include: Sequence[str],
        timeout_sec: float,
    ) -> JSONDict | None: ...

    async def get(
        self,
        *,
        conv_id: str,
        collection_name: str,
        ids: Sequence[str] | None,
        where: Mapping[str, JSONValue] | None,
        include: Sequence[str],
        timeout_sec: float,
    ) -> JSONDict | None: ...

    async def delete(
        self,
        *,
        conv_id: str,
        collection_name: str,
        ids: Sequence[str] | None,
        where: Mapping[str, JSONValue] | None,
        timeout_sec: float,
    ) -> None: ...

    async def delete_collection(
        self,
        *,
        conv_id: str,
        collection_name: str,
        timeout_sec: float,
    ) -> None: ...

    async def list_collections(self, *, timeout_sec: float) -> list[str]: ...

    async def list_collections_for_conv(self, *, conv_id: str, timeout_sec: float) -> list[str]: ...

    async def count(
        self,
        *,
        conv_id: str,
        collection_name: str,
        timeout_sec: float,
    ) -> int: ...

    async def resolve_active_collection_name(self, conv_id: str) -> str: ...


class MCPStorageProtocol(Protocol):

    database_files: DatabaseFilesProtocol
    event_bus: EventBusProtocol
    config: ConfigProtocol
    chroma_path: str
    embedding_timeout: int
    model_resolution_service: ModelResolutionServiceProtocol | None
    model_information_service: ModelInformationServiceProtocol | None
    metrics: MetricsManagerProtocol
    storage_manager: StorageManagerProtocol
    files: FilesPathResolverProtocol
    chroma: ChromaGatewayProtocol
    _sparse_index_lock_cache: WeakAsyncLRUCache[asyncio.Lock]
    _chroma_rw_lock_cache: WeakAsyncLRUCache[AsyncRWLock]

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    async def get_sparse_index_lock(self, conv_id: str) -> asyncio.Lock: ...

    async def get_chroma_rw_lock(self, conv_id: str) -> AsyncRWLock: ...


class EmbeddingProgressCallback(Protocol):
    def __call__(self, task_id: str, percent: int, message: str) -> Awaitable[None]: ...


class EmbeddingCancellationChecker(Protocol):
    def __call__(
        self,
        task_id: str,
        operation: str,
        token: CancellationTokenProtocol | None = None,
    ) -> Awaitable[None]: ...


class ChromaCollectionProtocol(Protocol): ...


class ChromaClientProtocol(Protocol):
    def get_collection(self, name: str) -> ChromaCollectionProtocol: ...

    def delete_collection(self, name: str) -> None: ...

    def get_or_create_collection(
        self,
        *,
        name: str,
        metadata: Mapping[str, JSONValue],
    ) -> ChromaCollectionProtocol: ...


class ChromaClientOwnerProtocol(Protocol):
    chroma_client: ChromaClientProtocol | None
