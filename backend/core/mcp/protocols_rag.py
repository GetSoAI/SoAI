"""SoAI - MCP RAG protocol contracts for cross-subsystem communication [backend/core/mcp/protocols_rag.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from core.concurrency.locks import AsyncRWLock

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict

__all__ = (
    "FetchedContentProtocol",
    "MCPRAGProtocol",
    "MCPRAGReindexLockRegistryProtocol",
    "MCPRAGStorageProtocol",
)


class MCPRAGReindexLockRegistryProtocol(Protocol):
    async def is_in_progress(self, lock_key: str) -> bool: ...


class MCPRAGWorkerProtocol(Protocol):
    @property
    def reindex_locks(self) -> MCPRAGReindexLockRegistryProtocol: ...


class FetchedContentProtocol(Protocol):
    @property
    def content(self) -> str: ...

    @property
    def content_type(self) -> str: ...

    @property
    def title(self) -> str | None: ...

    @property
    def page_count(self) -> int | None: ...

    @property
    def source_url(self) -> str | None: ...

    @property
    def source_html(self) -> str | None: ...


@runtime_checkable
class MCPRAGStorageProtocol(Protocol):
    chroma_path: str

    async def get_sparse_index_lock(self, conv_id: str) -> asyncio.Lock: ...

    async def get_chroma_rw_lock(self, conv_id: str) -> AsyncRWLock: ...


@runtime_checkable
class MCPRAGProtocol(Protocol):
    config: ConfigProtocol

    @property
    def storage(self) -> MCPRAGStorageProtocol: ...

    @property
    def worker(self) -> MCPRAGWorkerProtocol: ...

    async def get_collection_metadata(self, conv_id: str) -> JSONDict: ...

    async def resolve_conv_id_for_user(self, conv_id: str, user_id: int) -> str: ...

    async def is_embedding_model_available(self, model_id: str) -> bool: ...

    async def ensure_any_embedding_model_available(self) -> str: ...

    async def validate_and_resolve_embedding_model(self, model_id: str) -> tuple[str, int]: ...

    async def initialize(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def upload_document(
        self,
        *,
        conv_id: str,
        filename: str,
        content_base64: str,
        file_type: str,
        user_id: int,
        knowledge_attachment_id: str | None = None,
        knowledge_item_index: int | None = None,
        knowledge_source_type: str | None = None,
        knowledge_operation_type: str | None = None,
        client_batch_id: str | None = None,
    ) -> JSONDict: ...

    async def upload_document_from_path(
        self,
        *,
        conv_id: str,
        source_path: str,
        filename: str,
        file_type: str,
        user_id: int,
        existing_task_id: str | None = None,
        transfer_progress_start: int = 0,
        transfer_progress_end: int = 9,
        knowledge_attachment_id: str | None = None,
        knowledge_item_index: int | None = None,
        knowledge_source_type: str | None = None,
        knowledge_operation_type: str | None = None,
        client_batch_id: str | None = None,
    ) -> JSONDict: ...

    async def search(
        self,
        *,
        conv_id: str,
        query: str,
        top_k: int,
        similarity_threshold: float,
        retrieval_strategy: str,
        user_id: int,
    ) -> JSONDict: ...

    async def delete_document(self, conv_id: str, document_id: str) -> bool: ...

    async def reindex_conversation(self, conv_id: str, user_id: int, model_id: str) -> JSONDict: ...
