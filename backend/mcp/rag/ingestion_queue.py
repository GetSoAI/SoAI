"""SoAI - MCP RAG ingestion queueing [backend/mcp/rag/ingestion_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_paths_mcp_rag import (
    MCP_RAG_COUNTER_DOCUMENTS_WEB_FETCH_INGESTS_QUEUED,
    MCP_RAG_GAUGE_PROCESSING_QUEUE_SIZE,
)
from core.tasks.enums import TaskStatus
from core.tasks.task_cancellation import cancel
from core.tasks.type_catalog import TASK_TYPE_RAG_WEB_FETCH_INGEST
from core.types.json import JSONDict
from mcp.progress_reporting import (
    cleanup_rag_document_entry,
    cleanup_task_registry_entry,
    create_rag_task,
)
from mcp.rag.ingestion_validation import derive_filename_from_url
from mcp.rag.internal_protocols import MCPRAGInternalProtocol
from mcp.rag.knowledge_prompt_events import record_knowledge_prompt_event_and_publish
from mcp.rag.request_models import WebFetchIngestRequest
from mcp.worker.document_entry import create_rag_document_entry
from mcp.worker.durable_enqueue import create_durable_rag_job_and_wake_worker
from mcp.worker.metrics_reporting import (
    record_worker_metric_counter,
    record_worker_metric_gauge,
)
from mcp.worker.processing.job_types import WEB_FETCH_INGEST_JOB_TYPE

__all__ = ("enqueue_web_fetch_ingest_job",)


async def enqueue_web_fetch_ingest_job(
    *,
    rag_service: MCPRAGInternalProtocol,
    request: WebFetchIngestRequest,
    logger: LoggerProtocol,
) -> JSONDict:
    doc_id = str(uuid.uuid4())
    db_entry_created = False
    task_id: str | None = None
    queued = False
    try:
        task = await create_rag_task(
            rag_service.task_registry,
            task_type=TASK_TYPE_RAG_WEB_FETCH_INGEST,
            user_id=request.user_id,
            conv_id=request.conv_id,
            status=TaskStatus.PENDING,
            progress_total=100,
            metadata={"document_id": doc_id, "url": request.canonical_url},
        )
        task_id = task.task_id
        await create_rag_document_entry(
            rag_service.worker,
            doc_id=doc_id,
            conv_id=request.conv_id,
            user_id=request.user_id,
            filename=derive_filename_from_url(request.canonical_url),
            file_type="url",
            file_size_bytes=0,
            status="queued",
            source_type="url",
            source_url=request.canonical_url,
            chunking_strategy=request.chunking_strategy,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            embedding_model=request.embedding_model,
            metadata={"task_id": task_id},
        )
        db_entry_created = True
        queue_payload: JSONDict = {
            "type": WEB_FETCH_INGEST_JOB_TYPE,
            "conv_id": request.conv_id,
            "document_id": doc_id,
            "task_id": task_id,
            "user_id": request.user_id,
            "file_type": "url",
            "url": request.canonical_url,
            "focus_query": request.normalized_focus_query,
            "retrieval_strategy": request.normalized_strategy,
            "top_k": request.top_k,
            "similarity_threshold": request.similarity_threshold,
            "chunk_size": request.chunk_size,
            "chunk_overlap": request.chunk_overlap,
            "embedding_model": request.embedding_model,
            "chunking_strategy": request.chunking_strategy,
            "return_extract_mode": request.normalized_return_extract_mode,
            "return_max_chars": request.return_max_chars,
        }
        await create_durable_rag_job_and_wake_worker(
            rag_service.worker,
            job_type=WEB_FETCH_INGEST_JOB_TYPE,
            conv_id=request.conv_id,
            user_id=request.user_id,
            document_id=doc_id,
            task_id=task_id,
            payload=queue_payload,
            spool_path=None,
            logger=logger,
        )
        queued = True
        record_worker_metric_counter(
            rag_service.metrics,
            logger,
            MCP_RAG_COUNTER_DOCUMENTS_WEB_FETCH_INGESTS_QUEUED,
            operation="mcp.rag.ingestion_queue.queue",
            details={"document_id": doc_id, "conv_id": request.conv_id},
        )
        record_worker_metric_gauge(
            rag_service.metrics,
            logger,
            MCP_RAG_GAUGE_PROCESSING_QUEUE_SIZE,
            operation="mcp.rag.ingestion_queue.queue",
            details={"document_id": doc_id, "conv_id": request.conv_id},
            value=rag_service.worker.processing_queue.qsize(),
        )
        filename = derive_filename_from_url(request.canonical_url)
        await record_knowledge_prompt_event_and_publish(
            database_knowledge_prompt_state=rag_service.database_knowledge_prompt_state,
            event_bus=rag_service.event_bus,
            logger=logger,
            conv_id=request.conv_id,
            user_id=request.user_id,
            event_type="documents_added",
            document_names=(filename,),
            document_count=1,
            details={"document_id": doc_id, "source_type": "url", "task_id": task_id},
            operation="mcp.rag.ingestion_queue.knowledge_prompt_event",
        )
        return {"document_id": doc_id, "task_id": task_id, "status": "queued"}
    finally:
        if not queued:
            if task_id is not None:

                async def cancel_task() -> None:
                    _ = await cancel(
                        rag_service.task_registry,
                        task_id,
                        reason="URL ingestion failed before queue delivery.",
                    )

                await uncancel_then_cleanup(
                    cleanup_task_registry_entry(
                        task_id,
                        cancel_task,
                        logger=logger,
                    ),
                )
            if db_entry_created:
                await uncancel_then_cleanup(
                    cleanup_rag_document_entry(
                        doc_id,
                        request.conv_id,
                        rag_service.database_files,
                        logger=logger,
                    ),
                )
