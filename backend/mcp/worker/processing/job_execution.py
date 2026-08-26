"""SoAI - MCP worker durable job dispatch and execution [backend/mcp/worker/processing/job_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.protocols import LoggerProtocol
from core.tasks.cancellation_token_scope import cancellation_token_scope
from mcp.worker.document_job_processor import process_document_job
from mcp.worker.processing.job_types import RAG_DOCUMENT_JOB_TYPES, REINDEX_JOB_TYPE
from mcp.worker.processors.reindex_handler import process_reindex

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from mcp.worker.internal_protocols import MCPWorkerProtocol
    from mcp.worker.processing.job_parsing import ParsedProcessingJob

__all__ = ("execute_processing_job",)


async def execute_processing_job(
    self: MCPWorkerProtocol,
    job: ParsedProcessingJob,
    *,
    logger: LoggerProtocol,
) -> str | None:
    if job.job_type in RAG_DOCUMENT_JOB_TYPES:
        return await process_document_job(
            self,
            job.payload,
            task_id=job.task_id,
            job_type=job.job_type,
            logger=logger,
        )
    if job.job_type == REINDEX_JOB_TYPE:
        token: CancellationTokenProtocol | None
        task = await self.task_registry.get(job.task_id)
        if task is not None:
            async with cancellation_token_scope(
                self.token_collection,
                self.cancellation_history,
                self.cancellation_event_bus,
                cancellation_id=task.cancellation_id,
                owner="rag:reindex",
                metadata={"task_id": job.task_id},
                logger=logger,
            ) as token:
                await process_reindex(self, job.payload, job.task_id, token=token)
        else:
            await process_reindex(self, job.payload, job.task_id, token=None)
        return None
    raise ValueError(f"Unknown job type: {job.job_type}")
