"""SoAI - MCP worker processing cancellation cleanup [backend/mcp/worker/processing/job_cancellation_postmortem.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.tasks.enums import TaskStatus
from mcp.worker.knowledge_prompt_recording import record_document_knowledge_prompt_event
from mcp.worker.processing.durable_job_payloads import lease_identity_from_job_payload
from mcp.worker.processing.job_failure_notifications import publish_document_cancelled_event
from mcp.worker.processing.job_failure_resolution import FAILED_FAILURE_DETAILS, resolve_document_id
from mcp.worker.processing.job_terminal_operations import try_mark_rag_document_terminal_status
from mcp.worker.processing.job_types import RAG_DOCUMENT_JOB_TYPES, RAG_PROCESSING_JOB_TYPES

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "finalize_worker_cancellation",
    "handle_token_cancellation",
)

OPERATION_CANCEL_CLEANUP = "mcp.worker.processing_worker.cancel_cleanup"
OPERATION_TOKEN_CANCEL_TASK = "mcp.worker.processing_worker.token_cancel.cancel_task"
OPERATION_TOKEN_CANCEL_DOCUMENT = "mcp.worker.processing_worker.token_cancel.document"


async def finalize_worker_cancellation(
    self: MCPWorkerProtocol,
    *,
    worker_id: int,
    task_id: str | None,
    job_type: str | None,
    document_id: str | None,
    job_payload: JSONDict | None,
    logger: LoggerProtocol,
) -> None:
    if not task_id:
        return
    resolved_document_id = resolve_document_id(document_id, job_payload)
    job_id, lease_token = lease_identity_from_job_payload(job_payload)
    task_cancelled = False
    try:
        task = await self.task_registry.get(task_id)
        task_cancelled = bool(task and task.status == TaskStatus.CANCELLED)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION_CANCEL_CLEANUP)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to finalize tasks during cancellation handling (non-critical).",
            operation=OPERATION_CANCEL_CLEANUP,
            details={"task_id": task_id, "job_type": job_type, "worker_id": worker_id},
            level="debug",
        )
    if task_cancelled:
        if job_type in RAG_DOCUMENT_JOB_TYPES and resolved_document_id:
            terminal_status_owned = await try_mark_rag_document_terminal_status(
                self,
                resolved_document_id,
                rag_status="cancelled",
                status_details=FAILED_FAILURE_DETAILS,
                error_message="Cancelled by user",
                job_id=job_id,
                lease_token=lease_token,
                logger=logger,
                worker_id=worker_id,
                task_id=task_id,
                job_type=job_type,
                operation=OPERATION_CANCEL_CLEANUP,
            )
            if not terminal_status_owned:
                return
        return
    if job_type in RAG_DOCUMENT_JOB_TYPES and resolved_document_id:
        terminal_status_owned = await try_mark_rag_document_terminal_status(
            self,
            resolved_document_id,
            rag_status="error",
            status_details=FAILED_FAILURE_DETAILS,
            error_message="Worker shutdown",
            job_id=job_id,
            lease_token=lease_token,
            logger=logger,
            worker_id=worker_id,
            task_id=task_id,
            job_type=job_type,
            operation=OPERATION_CANCEL_CLEANUP,
        )
        if not terminal_status_owned:
            return
    if job_type in RAG_PROCESSING_JOB_TYPES:
        try:
            await self.fail_task(task_id, "Worker shutdown")
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION_CANCEL_CLEANUP)
            log_handled_exception(
                logger,
                coerced,
                message="Failed to fail task during worker shutdown.",
                operation=OPERATION_CANCEL_CLEANUP,
                details={"task_id": task_id, "job_type": job_type, "worker_id": worker_id},
                level="warning",
            )


async def handle_token_cancellation(
    self: MCPWorkerProtocol,
    cancelled_error: TaskCancelledError,
    *,
    worker_id: int,
    task_id: str | None,
    job_type: str | None,
    document_id: str | None,
    job_payload: JSONDict | None,
    logger: LoggerProtocol,
) -> bool:
    logger.debug(
        "Worker %s token-cancelled for task %s: %s",
        worker_id,
        task_id or "unknown",
        cancelled_error.reason,
    )
    resolved_document_id = resolve_document_id(document_id, job_payload)
    job_id, lease_token = lease_identity_from_job_payload(job_payload)
    if task_id and job_type in RAG_DOCUMENT_JOB_TYPES and resolved_document_id:
        terminal_status_owned = await try_mark_rag_document_terminal_status(
            self,
            resolved_document_id,
            rag_status="cancelled",
            status_details=FAILED_FAILURE_DETAILS,
            error_message="Cancelled by user",
            job_id=job_id,
            lease_token=lease_token,
            logger=logger,
            worker_id=worker_id,
            task_id=task_id,
            job_type=job_type,
            operation=OPERATION_TOKEN_CANCEL_DOCUMENT,
        )
        if not terminal_status_owned:
            return False
    if task_id and job_type in RAG_PROCESSING_JOB_TYPES:
        try:
            await self.cancel_task(task_id, cancelled_error.reason)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION_TOKEN_CANCEL_TASK)
            log_handled_exception(
                logger,
                coerced,
                message="Failed to cancel task after token cancellation (non-critical).",
                operation=OPERATION_TOKEN_CANCEL_TASK,
                details={"task_id": task_id, "job_type": job_type, "worker_id": worker_id},
                level="debug",
            )
    if task_id and job_type in RAG_DOCUMENT_JOB_TYPES and resolved_document_id:
        await publish_document_cancelled_event(
            self,
            document_id=resolved_document_id,
            conv_id=str(job_payload.get("conv_id") or "").strip() if job_payload else "",
            task_id=task_id,
            reason=cancelled_error.reason,
            logger=logger,
            worker_id=worker_id,
            job_type=job_type,
            operation=OPERATION_TOKEN_CANCEL_DOCUMENT,
        )
        await record_document_knowledge_prompt_event(
            self,
            logger=logger,
            job={} if job_payload is None else job_payload,
            document_id=resolved_document_id,
            conv_id=str(job_payload.get("conv_id") or "").strip() if job_payload else "",
            task_id=task_id,
            event_type="document_processing_cancelled",
            detail_message=cancelled_error.reason,
            operation=OPERATION_TOKEN_CANCEL_DOCUMENT,
        )
    return True
