"""SoAI - MCP RAG document upload ingestion [backend/mcp/rag/document_upload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.rag.upload_preparation import (
    prepare_document_upload,
    resolve_upload_source,
)
from mcp.worker.path_upload import upload_worker_document_from_path
from mcp.worker.upload import upload_document_from_base64

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "upload_document",
    "upload_document_from_path",
)


async def upload_document(
    rag_service: MCPRAGInternalProtocol,
    conv_id: str,
    user_id: int,
    filename: str,
    content_base64: str,
    file_type: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    embedding_model: str | None = None,
    chunking_strategy: str = "token_based",
    knowledge_attachment_id: str | None = None,
    knowledge_item_index: int | None = None,
    knowledge_source_type: str | None = None,
    knowledge_operation_type: str | None = None,
    client_batch_id: str | None = None,
) -> JSONDict:
    prepared_upload = await prepare_document_upload(
        rag_service,
        conv_id=conv_id,
        user_id=user_id,
        file_type=file_type,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,
        chunking_strategy=chunking_strategy,
    )
    return await upload_document_from_base64(
        rag_service.worker,
        conv_id=prepared_upload.conv_id,
        user_id=user_id,
        filename=filename,
        file_type=prepared_upload.file_type,
        content_base64=content_base64,
        max_bytes=prepared_upload.max_upload_bytes,
        chunk_size=prepared_upload.chunk_size,
        chunk_overlap=prepared_upload.chunk_overlap,
        embedding_model=prepared_upload.resolved_embedding_model,
        chunking_strategy=prepared_upload.chunking_strategy,
        knowledge_attachment_id=knowledge_attachment_id,
        knowledge_item_index=knowledge_item_index,
        knowledge_source_type=knowledge_source_type,
        knowledge_operation_type=knowledge_operation_type,
        client_batch_id=client_batch_id,
    )


async def upload_document_from_path(
    rag_service: MCPRAGInternalProtocol,
    conv_id: str,
    user_id: int,
    source_path: str,
    filename: str,
    file_type: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    embedding_model: str | None = None,
    chunking_strategy: str = "token_based",
    existing_task_id: str | None = None,
    transfer_progress_start: int = 0,
    transfer_progress_end: int = 9,
    knowledge_attachment_id: str | None = None,
    knowledge_item_index: int | None = None,
    knowledge_source_type: str | None = None,
    knowledge_operation_type: str | None = None,
    client_batch_id: str | None = None,
) -> JSONDict:
    prepared_upload = await prepare_document_upload(
        rag_service,
        conv_id=conv_id,
        user_id=user_id,
        file_type=file_type,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,
        chunking_strategy=chunking_strategy,
    )
    resolved_source = resolve_upload_source(
        source_path,
        prepared_upload.max_upload_bytes,
    )
    return await upload_worker_document_from_path(
        rag_service.worker,
        conv_id=prepared_upload.conv_id,
        user_id=user_id,
        source_path=resolved_source,
        filename=filename,
        file_type=prepared_upload.file_type,
        chunk_size=prepared_upload.chunk_size,
        chunk_overlap=prepared_upload.chunk_overlap,
        embedding_model=prepared_upload.resolved_embedding_model,
        chunking_strategy=prepared_upload.chunking_strategy,
        existing_task_id=existing_task_id,
        transfer_progress_start=transfer_progress_start,
        transfer_progress_end=transfer_progress_end,
        knowledge_attachment_id=knowledge_attachment_id,
        knowledge_item_index=knowledge_item_index,
        knowledge_source_type=knowledge_source_type,
        knowledge_operation_type=knowledge_operation_type,
        client_batch_id=client_batch_id,
    )
