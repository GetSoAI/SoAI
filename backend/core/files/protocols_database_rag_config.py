"""SoAI - RAG configuration database protocol [backend/core/files/protocols_database_rag_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.database.requests import UpdateRAGConfigRequest, UpdateRAGConfigWithDefaultsRequest
from core.files.database_types import (
    RAGConfigWithDefaultsResult,
    RAGConversationConfigRecord,
    RAGVectorCollectionMetadataRecord,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DatabaseRAGConfigProtocol",)


class DatabaseRAGConfigProtocol(Protocol):
    async def get_rag_config(self, conv_id: str) -> RAGConversationConfigRecord | None: ...

    async def update_rag_config(self, request: UpdateRAGConfigRequest) -> None: ...

    async def update_rag_config_with_defaults(
        self,
        request: UpdateRAGConfigWithDefaultsRequest,
    ) -> RAGConfigWithDefaultsResult: ...

    async def get_rag_collection_metadata(
        self,
        conv_id: str,
    ) -> RAGVectorCollectionMetadataRecord | None: ...

    async def update_rag_collection_metadata(
        self,
        collection_id: str,
        conv_id: str,
        collection_name: str,
        embedding_model: str,
        embedding_dimensions: int,
        document_count: int,
        chunk_count: int,
        metadata: JSONDict | None = None,
    ) -> None: ...

    async def activate_rag_collection(
        self,
        collection_id: str,
        conv_id: str,
        collection_name: str,
        embedding_model: str,
        embedding_dimensions: int,
        document_count: int,
        chunk_count: int,
        metadata: JSONDict | None = None,
    ) -> None: ...

    async def delete_rag_collection_metadata_for_conversation(self, conv_id: str) -> None: ...
