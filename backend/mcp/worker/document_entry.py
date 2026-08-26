"""SoAI - MCP worker document entry creation [backend/mcp/worker/document_entry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.requests import CreateRAGDocumentRequest
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from mcp.worker.knowledge_attachment_events import (
    publish_worker_knowledge_attachment_changed_noncritical,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("create_rag_document_entry",)


def _metadata_text(metadata: JSONDict | None, key: str) -> str | None:
    if metadata is None:
        return None
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"RAG document metadata field {key} must be a non-empty string.")
    return value.strip()


def _metadata_item_index(metadata: JSONDict | None) -> int | None:
    if metadata is None:
        return None
    value = metadata.get("knowledge_item_index")
    if value is None:
        return None
    if not is_strict_int(value) or value < 0:
        raise ValidationError("RAG document metadata field knowledge_item_index is invalid.")
    return value


async def create_rag_document_entry(
    self: MCPWorkerProtocol,
    *,
    doc_id: str,
    conv_id: str,
    user_id: int,
    filename: str,
    file_type: str,
    file_size_bytes: int,
    status: str,
    source_type: str,
    source_url: str | None,
    chunking_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
    metadata: JSONDict | None,
) -> None:
    request = CreateRAGDocumentRequest(
        doc_id=doc_id,
        conv_id=conv_id,
        user_id=user_id,
        file_id=None,
        filename=filename,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        status=status,
        source_type=source_type,
        source_url=source_url,
        chunking_strategy=chunking_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,
        metadata=metadata,
    )
    knowledge_attachment_id = _metadata_text(metadata, "knowledge_attachment_id")
    if knowledge_attachment_id is None:
        await self.database_files.create_rag_document(request)
        return
    item_index = _metadata_item_index(metadata)
    if item_index is None:
        raise ValidationError("knowledge_item_index is required for knowledge attachment uploads.")
    operation_type = _metadata_text(metadata, "knowledge_operation_type") or "added"
    _, summary = await self.database_files.create_rag_document_with_knowledge_item(
        request,
        knowledge_attachment_id=knowledge_attachment_id,
        item_index=item_index,
        operation_type=operation_type,
    )
    await publish_worker_knowledge_attachment_changed_noncritical(
        self.event_bus,
        summary=summary,
        operation="mcp.worker.create_rag_document_entry.knowledge_event",
    )
