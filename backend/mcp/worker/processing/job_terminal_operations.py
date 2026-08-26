"""SoAI - MCP worker processing resilient terminal update operations [backend/mcp/worker/processing/job_terminal_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.rag.job_operations import (
    RAGDocumentStatusJobUpdateRequest,
    RAGDocumentStatusUpdateRequest,
)
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from mcp.worker.processing.durable_job_runtime import is_durable_processing_lease_lost
from mcp.worker.processing.job_failure_logging import log_processing_noncritical_failure
from mcp.worker.processing.job_failure_resolution import resolve_error_code

if TYPE_CHECKING:
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "finalize_failed_task",
    "mark_rag_document_terminal_status",
    "try_finalize_failed_task",
    "try_mark_rag_document_terminal_status",
)


async def finalize_failed_task(
    self: MCPWorkerProtocol,
    task_id: str,
    error: SoAIError,
) -> None:
    await finalize(
        self.task_registry,
        task_id,
        TaskStatus.FAILED,
        error_code=resolve_error_code(error),
        error_message=error.message,
        status_message=error.message,
    )


async def try_finalize_failed_task(
    self: MCPWorkerProtocol,
    task_id: str,
    error: SoAIError,
    *,
    logger: LoggerProtocol,
    worker_id: int,
    job_type: str | None,
    operation: str,
) -> None:
    try:
        await finalize_failed_task(self, task_id, error)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_processing_noncritical_failure(
            logger,
            exception,
            message="Failed to finalize failed RAG processing task.",
            operation=operation,
            details={"task_id": task_id, "job_type": job_type, "worker_id": worker_id},
        )


async def mark_rag_document_terminal_status(
    self: MCPWorkerProtocol,
    document_id: str,
    *,
    rag_status: str,
    status_details: str,
    error_message: str,
    job_id: str | None,
    lease_token: str | None,
) -> bool:
    document = await self.database_files.get_rag_document_by_id(document_id)
    if document is None or document.get("status") == "completed":
        return False
    if rag_status not in {"error", "cancelled"}:
        return False
    if job_id and lease_token:
        await self.update_rag_document_status_for_job(
            RAGDocumentStatusJobUpdateRequest(
                status_update=RAGDocumentStatusUpdateRequest(
                    doc_id=document_id,
                    status=rag_status,
                    status_details=status_details,
                    error_message=error_message,
                ),
                job_id=job_id,
                lease_token=lease_token,
            ),
        )
        return True
    await self.update_rag_document_status(
        RAGDocumentStatusUpdateRequest(
            doc_id=document_id,
            status=rag_status,
            status_details=status_details,
            error_message=error_message,
        ),
    )
    return True


async def try_mark_rag_document_terminal_status(
    self: MCPWorkerProtocol,
    document_id: str,
    *,
    rag_status: str,
    status_details: str,
    error_message: str,
    job_id: str | None,
    lease_token: str | None,
    logger: LoggerProtocol,
    worker_id: int,
    task_id: str | None,
    job_type: str | None,
    operation: str,
) -> bool:
    try:
        return await mark_rag_document_terminal_status(
            self,
            document_id,
            rag_status=rag_status,
            status_details=status_details,
            error_message=error_message,
            job_id=job_id,
            lease_token=lease_token,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if isinstance(exception, SoAIError) and is_durable_processing_lease_lost(exception):
            return False
        log_processing_noncritical_failure(
            logger,
            exception,
            message="Failed to update terminal RAG document state.",
            operation=operation,
            details={"task_id": task_id, "job_type": job_type, "worker_id": worker_id},
        )
    return True
