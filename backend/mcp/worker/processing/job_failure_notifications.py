"""SoAI - MCP worker processing failure event and telemetry operations [backend/mcp/worker/processing/job_failure_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_mcp import (
    RAGDocumentProcessingCancelledEvent,
    RAGDocumentProcessingFailedEvent,
)
from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_paths_mcp_rag import (
    MCP_RAG_COUNTER_DOCUMENTS_UPLOADS_FAILED,
    MCP_RAG_COUNTER_DOCUMENTS_WEB_FETCH_INGESTS_FAILED,
)
from mcp.worker.metrics_reporting import record_worker_metric_counter
from mcp.worker.processing.job_failure_logging import log_processing_noncritical_failure
from mcp.worker.processing.job_types import (
    DOCUMENT_UPLOAD_JOB_TYPE,
    RAG_DOCUMENT_JOB_TYPES,
)

if TYPE_CHECKING:
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "publish_document_cancelled_event",
    "publish_document_failed_event",
    "record_document_failure_metric",
)


async def publish_document_cancelled_event(
    self: MCPWorkerProtocol,
    *,
    document_id: str,
    conv_id: str,
    task_id: str,
    reason: str,
    logger: LoggerProtocol,
    worker_id: int,
    job_type: str | None,
    operation: str,
) -> None:
    try:
        await self.event_bus.publish(
            RAGDocumentProcessingCancelledEvent(
                document_id=document_id,
                conv_id=conv_id,
                task_id=task_id,
                reason=reason,
            ),
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_processing_noncritical_failure(
            logger,
            exception,
            message="Failed to publish cancelled RAG document event.",
            operation=operation,
            details={"task_id": task_id, "job_type": job_type, "worker_id": worker_id},
        )


async def publish_document_failed_event(
    self: MCPWorkerProtocol,
    *,
    document_id: str,
    conv_id: str,
    task_id: str,
    error_message: str,
    error_type: str,
    logger: LoggerProtocol,
    worker_id: int,
    job_type: str | None,
    operation: str,
) -> None:
    try:
        await self.event_bus.publish(
            RAGDocumentProcessingFailedEvent(
                document_id=document_id,
                conv_id=conv_id,
                task_id=task_id,
                error_message=error_message,
                error_type=error_type,
            ),
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_processing_noncritical_failure(
            logger,
            exception,
            message="Failed to publish failed RAG document event.",
            operation=operation,
            details={"task_id": task_id, "job_type": job_type, "worker_id": worker_id},
        )


def record_document_failure_metric(
    self: MCPWorkerProtocol,
    *,
    job_type: str | None,
    logger: LoggerProtocol,
    worker_id: int,
    task_id: str,
    operation: str,
) -> None:
    if job_type not in RAG_DOCUMENT_JOB_TYPES:
        return
    failure_counter = (
        MCP_RAG_COUNTER_DOCUMENTS_UPLOADS_FAILED
        if job_type == DOCUMENT_UPLOAD_JOB_TYPE
        else MCP_RAG_COUNTER_DOCUMENTS_WEB_FETCH_INGESTS_FAILED
    )
    record_worker_metric_counter(
        self.metrics,
        logger,
        failure_counter,
        operation=operation,
        details={"task_id": task_id, "job_type": job_type, "worker_id": worker_id},
    )
