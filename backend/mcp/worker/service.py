"""SoAI - MCP worker service [backend/mcp/worker/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.protocols import FileParserProtocol
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.status_transitions import update_progress
from core.tasks.task_cancellation import cancel
from mcp.worker.dependencies import MCPWorkerDependencies
from mcp.worker.knowledge_attachment_events import (
    publish_worker_knowledge_attachment_changed_noncritical,
)
from mcp.worker.processing.worker_loop import processing_worker
from mcp.worker.rag_status_updates import (
    publish_rag_document_status_update,
    publish_rag_document_status_update_for_job,
)
from mcp.worker.reindex_lock_registry import (
    ReindexLockRegistry,
    ReindexLockRegistryDependencies,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.rag.job_operations import (
        RAGDocumentStatusJobUpdateRequest,
        RAGDocumentStatusUpdateRequest,
    )
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = ("MCPWorker",)

LOGGER_NAME = "SoAI.mcp.worker.service"
OPERATION_MCP_WORKER_TASK_LIFECYCLE_CHECK_CANCELLATION = (
    "mcp.worker.task_lifecycle.check_cancellation"
)
OPERATION_MCP_WORKER_TASK_LIFECYCLE_REPORT_PROGRESS = "mcp.worker.task_lifecycle.report_progress"
OPERATION_MCP_WORKER_STOP_WORKERS = "mcp.worker.service.stop_workers"


class MCPWorker:

    def __init__(self, deps: MCPWorkerDependencies) -> None:
        self._deps = deps
        self.database_files = deps.database_files
        self.database_conversation_knowledge_attachments = (
            deps.database_conversation_knowledge_attachments
        )
        self.database_knowledge_prompt_state = deps.database_knowledge_prompt_state
        self.event_bus = deps.event_bus
        self.config = deps.config
        self.storage_manager = deps.storage_manager
        self.shutdown_event = deps.shutdown_event
        self.task_registry = deps.task_registry
        self.storage = deps.storage
        self.mcp_search = deps.mcp_search
        self.cancellation_history = deps.cancellation_history
        self.cancellation_event_bus = deps.cancellation_event_bus
        self.token_collection = deps.token_collection
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker
        self.parsers: dict[str, FileParserProtocol] = {}
        self.chunker = deps.chunker
        self.processing_queue: asyncio.Queue[JSONDict] = asyncio.Queue(
            maxsize=deps.config.get_int("TOOLS.RAG.PROCESSING_QUEUE_SIZE"),
        )
        self.processing_workers: list[asyncio.Task[None]] = []
        self.worker_count = deps.processing_workers
        self.metrics = deps.metrics_manager
        self.reindex_locks = ReindexLockRegistry(ReindexLockRegistryDependencies())

    async def update_rag_document_status(
        self,
        request: RAGDocumentStatusUpdateRequest,
    ) -> None:
        await publish_rag_document_status_update(
            self,
            request,
        )

    async def update_rag_document_status_for_job(
        self,
        request: RAGDocumentStatusJobUpdateRequest,
    ) -> None:
        await publish_rag_document_status_update_for_job(
            self,
            request,
        )

    async def finalize_knowledge_attachment_task(
        self,
        *,
        task_id: str,
        processing_state: str,
        terminal_item_status: str,
        error_message: str | None,
    ) -> None:
        summary = (
            await (
                self.database_conversation_knowledge_attachments.finalize_knowledge_attachment_task(
                    task_id=task_id,
                    processing_state=processing_state,
                    terminal_item_status=terminal_item_status,
                    error_message=error_message,
                )
            )
        )
        if summary is not None:
            await publish_worker_knowledge_attachment_changed_noncritical(
                self.event_bus,
                summary=summary,
                operation="mcp.worker.finalize_knowledge_attachment_task.knowledge_event",
            )

    def init_parsers(self) -> None:
        self.parsers = self._deps.parser_registry_factory()

    def start_workers(self) -> None:
        logger = get_logger(LOGGER_NAME)
        for worker_id in range(self.worker_count):
            worker = spawn_tracked_task(
                processing_worker(self, worker_id),
                name=f"mcp-processing-worker-{worker_id}",
                logger=logger,
                cancellation_binder=self._cancellation_binder,
                cancellation_id=build_soai_id(
                    (
                        "sys",
                        "mcp",
                        "processing_worker",
                        safe_or_hashed_segment(str(worker_id)),
                    ),
                ),
                owner="mcp_processing_worker",
                finalizer_tracker=self._finalizer_tracker,
            )
            self.processing_workers.append(worker)

    async def stop_workers(self) -> None:
        for worker in self.processing_workers:
            worker.cancel()
        if self.processing_workers:
            cleanup_results = await asyncio.gather(*self.processing_workers, return_exceptions=True)
            logger = get_logger(LOGGER_NAME)
            for cleanup_result in cleanup_results:
                if isinstance(cleanup_result, asyncio.CancelledError):
                    continue
                if isinstance(cleanup_result, BaseException):
                    log_handled_exception(
                        logger,
                        cleanup_result,
                        message="MCP worker task raised during shutdown cleanup (non-critical).",
                        operation=OPERATION_MCP_WORKER_STOP_WORKERS,
                        level="warning",
                    )
        self.processing_workers.clear()

    async def complete_task(
        self,
        task_id: str,
        result: JSONDict | None = None,
        message: str = "Operation completed",
    ) -> Task | None:
        return await finalize(
            self.task_registry,
            task_id,
            TaskStatus.COMPLETED,
            result=result,
            status_message=message,
        )

    async def fail_task(self, task_id: str, error_message: str) -> None:
        await finalize(
            self.task_registry,
            task_id,
            TaskStatus.FAILED,
            error_code=500,
            error_message=error_message,
        )

    async def cancel_task(self, task_id: str, reason: str) -> None:
        normalized_reason = str(reason or "").strip() or "Cancelled by user"
        await cancel(self.task_registry, task_id, reason=normalized_reason)

    async def send_progress(
        self,
        task_id: str,
        percent: int,
        message: str,
        details: str = "",
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            await update_progress(
                self.task_registry,
                task_id,
                progress_current=percent,
                status_message=message,
                details=details,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to update task progress",
                operation=OPERATION_MCP_WORKER_TASK_LIFECYCLE_REPORT_PROGRESS,
                details={"task_id": task_id, "percent": percent},
                level="warning",
            )

    async def check_cancellation(
        self,
        task_id: str,
        operation: str,
        token: CancellationTokenProtocol | None = None,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        if token:
            token.raise_if_cancelled()
            return
        if not task_id:
            return
        try:
            task = await self.task_registry.get(task_id)
            if task and task.status == TaskStatus.CANCELLED:
                raise asyncio.CancelledError(f"Task cancelled during {operation}")
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Error checking task cancellation state.",
                operation=OPERATION_MCP_WORKER_TASK_LIFECYCLE_CHECK_CANCELLATION,
                details={"task_id": task_id, "operation": operation},
                level="warning",
            )
