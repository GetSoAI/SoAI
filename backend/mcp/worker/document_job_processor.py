"""SoAI - MCP document job processing helpers [backend/mcp/worker/document_job_processor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_mcp import (
    RAGDocumentProcessingCompletedEvent,
    RAGDocumentProcessingStartedEvent,
)
from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_paths_mcp_rag import (
    MCP_RAG_COUNTER_DOCUMENTS_UPLOADS_COMPLETED,
    MCP_RAG_COUNTER_DOCUMENTS_WEB_FETCH_INGESTS_COMPLETED,
    MCP_RAG_TIMING_DOCUMENT_PROCESSING_MS,
)
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.enums import TaskStatus
from core.tasks.status_transitions import update_status
from core.validation.integers import is_strict_int
from mcp.worker.knowledge_prompt_recording import record_document_knowledge_prompt_event
from mcp.worker.metrics_reporting import (
    record_worker_metric_counter,
    record_worker_metric_timing,
)
from mcp.worker.processing.durable_job_payloads import lease_identity_from_job_payload
from mcp.worker.processing.durable_job_runtime import renew_durable_processing_lease
from mcp.worker.processing.job_types import (
    DOCUMENT_UPLOAD_JOB_TYPE,
    RAG_DOCUMENT_JOB_TYPES,
    WEB_FETCH_INGEST_JOB_TYPE,
)
from mcp.worker.processors.document import process_uploaded_document
from mcp.worker.processors.web_fetch_ingest import process_web_fetch_ingest

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict, JSONValue
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("process_document_job",)

OPERATION = "mcp.worker.document_job_processor.update_status"
OPERATION_EVENT = "mcp.worker.document_job_processor.event"
OPERATION_METRICS = "mcp.worker.document_job_processor.metrics"


async def _publish_document_started_event(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    document_id: str,
    conv_id: str,
    task_id: str,
    source_type: str,
    file_type: str,
) -> None:
    try:
        await worker.event_bus.publish(
            RAGDocumentProcessingStartedEvent(
                document_id=document_id,
                conv_id=conv_id,
                task_id=task_id,
                source_type=source_type,
                file_type=file_type,
            ),
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION_EVENT)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to publish RAG document started event.",
            operation=OPERATION_EVENT,
            details={"task_id": task_id, "document_id": document_id},
            level="debug",
        )


async def _publish_document_completed_event(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    document_id: str,
    conv_id: str,
    task_id: str,
    chunks_created: int,
    processing_time_ms: int,
) -> None:
    try:
        await worker.event_bus.publish(
            RAGDocumentProcessingCompletedEvent(
                document_id=document_id,
                conv_id=conv_id,
                task_id=task_id,
                chunks_created=chunks_created,
                processing_time_ms=processing_time_ms,
            ),
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION_EVENT)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to publish RAG document completed event.",
            operation=OPERATION_EVENT,
            details={"task_id": task_id, "document_id": document_id},
            level="debug",
        )


def _record_completion_metrics(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    source_type: str,
    task_id: str,
    document_id: str,
    chunks_created: int,
    processing_time_ms: int,
) -> None:
    completion_counter = (
        MCP_RAG_COUNTER_DOCUMENTS_UPLOADS_COMPLETED
        if source_type == "upload"
        else MCP_RAG_COUNTER_DOCUMENTS_WEB_FETCH_INGESTS_COMPLETED
    )
    details: dict[str, JSONValue] = {
        "task_id": task_id,
        "document_id": document_id,
        "chunks_created": chunks_created,
    }
    record_worker_metric_counter(
        worker.metrics,
        logger,
        completion_counter,
        operation=OPERATION_METRICS,
        details=details,
    )
    record_worker_metric_timing(
        worker.metrics,
        logger,
        MCP_RAG_TIMING_DOCUMENT_PROCESSING_MS,
        operation=OPERATION_METRICS,
        details=details,
        duration_ms=float(processing_time_ms),
    )


async def process_document_job(
    worker: MCPWorkerProtocol,
    job: JSONDict,
    *,
    task_id: str,
    job_type: str,
    logger: LoggerProtocol,
) -> str:
    if job_type not in RAG_DOCUMENT_JOB_TYPES:
        raise ValidationError(f"Unsupported document job type: {job_type}")
    document_id_value = job.get("document_id")
    document_id = str(document_id_value or "").strip()
    if not document_id:
        raise ValidationError(f"Job missing document_id: {job}")
    conv_id = str(job.get("conv_id") or "").strip()
    source_type = "upload" if job_type == DOCUMENT_UPLOAD_JOB_TYPE else "url"
    file_type_value = job.get("file_type")
    file_type = str(file_type_value or "").strip()
    if not file_type:
        raise ValidationError(f"Job missing file_type: {job}")
    start_time = asyncio.get_running_loop().time()
    try:
        await update_status(
            worker.task_registry,
            task_id,
            TaskStatus.WORKING,
            status_message="Processing document...",
        )
    except RECOVERABLE_EXCEPTIONS as status_error:
        log_handled_exception(
            logger,
            status_error,
            message="Failed to update task status (non-critical).",
            operation=OPERATION,
            details={"task_id": task_id, "status": TaskStatus.WORKING},
            level="debug",
        )
    task = await worker.task_registry.get(task_id)

    async def _process_document_job(token: CancellationTokenProtocol | None) -> None:
        await _publish_document_started_event(
            worker,
            logger=logger,
            document_id=document_id,
            conv_id=conv_id,
            task_id=task_id,
            source_type=source_type,
            file_type=file_type,
        )
        chunks_created = 0
        status_details: str | None = None
        extraction_warnings: tuple[str, ...] = ()
        fetch_result_payload: JSONDict | None = None
        if job_type == DOCUMENT_UPLOAD_JOB_TYPE:
            upload_result = await process_uploaded_document(worker, job, task_id, token=token)
            chunks_created = upload_result.chunks_created
            status_details = upload_result.status_details
            extraction_warnings = upload_result.warnings
        elif job_type == WEB_FETCH_INGEST_JOB_TYPE:
            fetch_result_payload = await process_web_fetch_ingest(worker, job, task_id, token=token)
            if fetch_result_payload is not None:
                chunks_created_value = fetch_result_payload.get("chunks_created")
                if is_strict_int(chunks_created_value):
                    chunks_created = chunks_created_value
        processing_time_ms = max(
            0,
            int((asyncio.get_running_loop().time() - start_time) * 1000),
        )
        task_result: JSONDict = {
            "chunks_created": chunks_created,
            "processing_time_ms": processing_time_ms,
        }
        if status_details is not None:
            task_result["status_details"] = status_details
            task_result["extraction_warnings"] = list(extraction_warnings)
        if fetch_result_payload is not None:
            task_result.update(fetch_result_payload)
        job_id, lease_token = lease_identity_from_job_payload(job)
        if job_id and lease_token:
            await renew_durable_processing_lease(
                worker,
                job_id=job_id,
                lease_token=lease_token,
            )
        completed_task = await worker.complete_task(
            task_id,
            result=task_result,
            message="Document processed",
        )
        if completed_task is None or completed_task.status != TaskStatus.COMPLETED:
            return
        await _publish_document_completed_event(
            worker,
            logger=logger,
            document_id=document_id,
            conv_id=conv_id,
            task_id=task_id,
            chunks_created=chunks_created,
            processing_time_ms=processing_time_ms,
        )
        await record_document_knowledge_prompt_event(
            worker,
            logger=logger,
            job=job,
            document_id=document_id,
            conv_id=conv_id,
            task_id=task_id,
            event_type="document_processing_completed",
            detail_message="Document processed",
            operation="mcp.worker.document_job_processor.knowledge_prompt_event",
        )
        _record_completion_metrics(
            worker,
            logger=logger,
            source_type=source_type,
            task_id=task_id,
            document_id=document_id,
            chunks_created=chunks_created,
            processing_time_ms=processing_time_ms,
        )

    if task is None:
        await _process_document_job(token=None)
    else:
        async with cancellation_token_scope(
            worker.token_collection,
            worker.cancellation_history,
            worker.cancellation_event_bus,
            cancellation_id=task.cancellation_id,
            owner=f"rag:{job_type}",
            metadata={"task_id": task_id, "document_id": document_id},
            logger=logger,
        ) as token:
            await _process_document_job(token=token)
    return document_id
