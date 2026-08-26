"""SoAI - MCP worker RAG document status update flow [backend/mcp/worker/rag_document_status_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.rag.job_operations import (
    RAGDocumentStatusJobUpdateRequest,
    RAGDocumentStatusUpdateRequest,
)
from mcp.worker.processing.durable_job_runtime import renew_durable_processing_lease

if TYPE_CHECKING:
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("update_worker_rag_document_status",)


async def update_worker_rag_document_status(
    worker: MCPWorkerProtocol,
    *,
    document_id: str,
    status: str,
    job_id: str | None,
    lease_token: str | None,
    status_details: str | None = None,
    content_hash: str | None = None,
    total_chunks: int | None = None,
    processed_chunks: int | None = None,
    embedding_model: str | None = None,
    effective_embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
    error_message: str | None = None,
) -> None:
    status_update = RAGDocumentStatusUpdateRequest(
        doc_id=document_id,
        status=status,
        status_details=status_details,
        content_hash=content_hash,
        total_chunks=total_chunks,
        processed_chunks=processed_chunks,
        embedding_model=embedding_model,
        effective_embedding_model=effective_embedding_model,
        embedding_dimensions=embedding_dimensions,
        error_message=error_message,
    )
    if job_id and lease_token:
        await renew_durable_processing_lease(worker, job_id=job_id, lease_token=lease_token)
        await worker.update_rag_document_status_for_job(
            RAGDocumentStatusJobUpdateRequest(
                status_update=status_update,
                job_id=job_id,
                lease_token=lease_token,
            ),
        )
        return
    await worker.update_rag_document_status(status_update)
