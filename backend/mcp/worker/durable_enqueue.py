"""SoAI - Durable RAG job enqueue helpers [backend/mcp/worker/durable_enqueue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from core.logging.protocols import LoggerProtocol
from core.rag.job_operations import RAGJobCreateRequest
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("create_durable_rag_job_and_wake_worker",)


async def create_durable_rag_job_and_wake_worker(
    worker: MCPWorkerProtocol,
    *,
    job_type: str,
    conv_id: str,
    user_id: int,
    document_id: str | None,
    task_id: str,
    payload: JSONDict,
    spool_path: str | None,
    logger: LoggerProtocol,
) -> str:
    job_id = uuid.uuid4().hex
    durable_payload = dict(payload)
    durable_payload["job_id"] = job_id
    durable_payload["task_id"] = task_id
    durable_payload["type"] = job_type
    created = await worker.database_files.create_rag_processing_job(
        RAGJobCreateRequest(
            job_id=job_id,
            job_type=job_type,
            conv_id=conv_id,
            user_id=user_id,
            document_id=document_id,
            task_id=task_id,
            payload=durable_payload,
            spool_path=spool_path,
            now_ms=int(epoch_ms()),
        ),
    )
    if not created:
        return job_id
    try:
        worker.processing_queue.put_nowait(
            {
                "job_id": job_id,
                "type": job_type,
                "task_id": task_id,
            },
        )
    except asyncio.QueueFull:
        logger.debug("Durable RAG job queued without worker wake-up: %s", job_id)
    return job_id
