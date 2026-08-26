"""SoAI - MCP worker processing failure cleanup [backend/mcp/worker/processing/job_postmortem.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.logging.protocols import LoggerProtocol
from mcp.worker.knowledge_prompt_recording import record_document_knowledge_prompt_event
from mcp.worker.processing.durable_job_payloads import lease_identity_from_job_payload
from mcp.worker.processing.job_failure_notifications import (
    publish_document_failed_event,
    record_document_failure_metric,
)
from mcp.worker.processing.job_failure_resolution import (
    resolve_document_id,
    resolve_failure_details,
)
from mcp.worker.processing.job_terminal_operations import (
    try_finalize_failed_task,
    try_mark_rag_document_terminal_status,
)
from mcp.worker.processing.job_types import (
    RAG_DOCUMENT_JOB_TYPES,
    REINDEX_JOB_TYPE,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("handle_processing_failure",)
OPERATION_MCP_WORKER_PROCESSING_WORKER_FAILURE_CLEANUP = (
    "mcp.worker.processing_worker.failure_cleanup"
)


async def handle_processing_failure(
    self: MCPWorkerProtocol,
    error: Exception,
    *,
    worker_id: int,
    task_id: str | None,
    job_type: str | None,
    document_id: str | None,
    job_payload: JSONDict | None,
    logger: LoggerProtocol,
) -> bool:
    payload_for_logs: JSONDict = {} if job_payload is None else job_payload
    coerced = coerce_to_soai_error(error)
    if task_id and job_type in RAG_DOCUMENT_JOB_TYPES:
        resolved_document_id = resolve_document_id(document_id, payload_for_logs)
        job_id, lease_token = lease_identity_from_job_payload(payload_for_logs)
        if resolved_document_id:
            terminal_status_owned = await try_mark_rag_document_terminal_status(
                self,
                resolved_document_id,
                rag_status="error",
                status_details=resolve_failure_details(coerced),
                error_message=coerced.message,
                job_id=job_id,
                lease_token=lease_token,
                logger=logger,
                worker_id=worker_id,
                task_id=task_id,
                job_type=job_type,
                operation=OPERATION_MCP_WORKER_PROCESSING_WORKER_FAILURE_CLEANUP,
            )
            if not terminal_status_owned:
                return False
        await try_finalize_failed_task(
            self,
            task_id,
            coerced,
            logger=logger,
            worker_id=worker_id,
            job_type=job_type,
            operation=OPERATION_MCP_WORKER_PROCESSING_WORKER_FAILURE_CLEANUP,
        )
        if resolved_document_id:
            await publish_document_failed_event(
                self,
                document_id=resolved_document_id,
                conv_id=str(payload_for_logs.get("conv_id") or "").strip(),
                task_id=task_id,
                error_message=coerced.message,
                error_type=type(error).__name__,
                logger=logger,
                worker_id=worker_id,
                job_type=job_type,
                operation=OPERATION_MCP_WORKER_PROCESSING_WORKER_FAILURE_CLEANUP,
            )
            await record_document_knowledge_prompt_event(
                self,
                logger=logger,
                job=payload_for_logs,
                document_id=resolved_document_id,
                conv_id=str(payload_for_logs.get("conv_id") or "").strip(),
                task_id=task_id,
                event_type="document_processing_failed",
                detail_message=coerced.message,
                operation=OPERATION_MCP_WORKER_PROCESSING_WORKER_FAILURE_CLEANUP,
            )
        record_document_failure_metric(
            self,
            job_type=job_type,
            logger=logger,
            worker_id=worker_id,
            task_id=task_id,
            operation=OPERATION_MCP_WORKER_PROCESSING_WORKER_FAILURE_CLEANUP,
        )
        return True
    if task_id and job_type == REINDEX_JOB_TYPE:
        await try_finalize_failed_task(
            self,
            task_id,
            coerced,
            logger=logger,
            worker_id=worker_id,
            job_type=job_type,
            operation=OPERATION_MCP_WORKER_PROCESSING_WORKER_FAILURE_CLEANUP,
        )
        return True
    return True
