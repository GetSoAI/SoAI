"""SoAI - MCP worker queue upload cleanup operations [backend/mcp/worker/queue_upload_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.rag.job_operations import RAGDocumentStatusUpdateRequest

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "delete_unqueued_rag_document",
    "mark_unqueued_rag_document_error",
)


async def delete_unqueued_rag_document(
    worker: MCPWorkerProtocol,
    logger: LoggerProtocol,
    *,
    doc_id: str,
    conv_id: str,
    operation: str,
) -> None:
    try:
        await worker.database_files.delete_rag_document(doc_id, conv_id)
    except RECOVERABLE_EXCEPTIONS as cleanup_error:
        log_exception(
            logger,
            cleanup_error,
            message="Failed to cleanup unqueued RAG document.",
            operation=operation,
            details={"doc_id": doc_id, "conv_id": conv_id},
            level="warning",
        )
    except SoAIError as cleanup_error:
        log_exception(
            logger,
            cleanup_error,
            message="Failed to cleanup unqueued RAG document.",
            operation=operation,
            details={"doc_id": doc_id, "conv_id": conv_id},
            level="warning",
        )
    except UNEXPECTED_RUNTIME_EXCEPTIONS as cleanup_error:
        coerced = coerce_to_soai_error(cleanup_error, operation=operation)
        log_exception(
            logger,
            coerced,
            message="Unexpected failure while cleaning up unqueued RAG document.",
            operation=operation,
            details={"doc_id": doc_id, "conv_id": conv_id},
            level="warning",
        )


async def mark_unqueued_rag_document_error(
    worker: MCPWorkerProtocol,
    logger: LoggerProtocol,
    *,
    doc_id: str,
    error_message: str,
    operation: str,
) -> None:
    try:
        await worker.update_rag_document_status(
            RAGDocumentStatusUpdateRequest(
                doc_id=doc_id,
                status="error",
                status_details="queue_failed",
                error_message=error_message,
            ),
        )
    except RECOVERABLE_EXCEPTIONS as cleanup_error:
        log_exception(
            logger,
            cleanup_error,
            message="Failed to mark unqueued RAG document as failed.",
            operation=operation,
            details={"doc_id": doc_id},
            level="warning",
        )
    except SoAIError as cleanup_error:
        log_exception(
            logger,
            cleanup_error,
            message="Failed to mark unqueued RAG document as failed.",
            operation=operation,
            details={"doc_id": doc_id},
            level="warning",
        )
    except UNEXPECTED_RUNTIME_EXCEPTIONS as cleanup_error:
        coerced = coerce_to_soai_error(cleanup_error, operation=operation)
        log_exception(
            logger,
            coerced,
            message="Unexpected failure while marking unqueued RAG document failed.",
            operation=operation,
            details={"doc_id": doc_id},
            level="warning",
        )
