"""SoAI - MCP worker queue upload operations [backend/mcp/worker/queue_upload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_rag import (
    MCP_RAG_COUNTER_DOCUMENTS_UPLOADS_QUEUED,
    MCP_RAG_GAUGE_PROCESSING_QUEUE_SIZE,
)
from mcp.rag.knowledge_prompt_events import record_knowledge_prompt_event_and_publish
from mcp.worker.document_entry import create_rag_document_entry
from mcp.worker.durable_enqueue import create_durable_rag_job_and_wake_worker
from mcp.worker.metrics_reporting import (
    record_worker_metric_counter,
    record_worker_metric_gauge,
)
from mcp.worker.processing.job_types import DOCUMENT_UPLOAD_JOB_TYPE
from mcp.worker.queue_upload_cleanup import delete_unqueued_rag_document

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("create_db_entry_and_queue_upload",)

LOGGER_NAME = "SoAI.mcp.worker.queue_upload"
OPERATION = "mcp.worker.queue_upload.cleanup_orphaned_doc"


async def create_db_entry_and_queue_upload(
    self: MCPWorkerProtocol,
    doc_id: str,
    conv_id: str,
    user_id: int,
    filename: str,
    file_type: str,
    file_size: int,
    temp_file: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
    chunking_strategy: str,
    task_id: str,
    knowledge_attachment_id: str | None = None,
    knowledge_item_index: int | None = None,
    knowledge_source_type: str | None = None,
    knowledge_operation_type: str | None = None,
    client_batch_id: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    await create_rag_document_entry(
        self,
        doc_id=doc_id,
        conv_id=conv_id,
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        file_size_bytes=file_size,
        status="queued",
        source_type="upload",
        source_url=None,
        chunking_strategy=chunking_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,
        metadata={
            "task_id": task_id,
            "knowledge_attachment_id": knowledge_attachment_id,
            "knowledge_item_index": knowledge_item_index,
            "knowledge_source_type": knowledge_source_type,
            "knowledge_operation_type": knowledge_operation_type,
            "client_batch_id": client_batch_id,
        },
    )
    queue_payload: JSONDict = {
        "type": DOCUMENT_UPLOAD_JOB_TYPE,
        "document_id": doc_id,
        "task_id": task_id,
        "temp_file": temp_file,
        "file_size": file_size,
        "file_type": file_type,
        "conv_id": conv_id,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "embedding_model": embedding_model,
        "chunking_strategy": chunking_strategy,
        "user_id": user_id,
        "knowledge_attachment_id": knowledge_attachment_id,
        "knowledge_item_index": knowledge_item_index,
        "knowledge_source_type": knowledge_source_type,
        "knowledge_operation_type": knowledge_operation_type,
        "client_batch_id": client_batch_id,
    }
    try:
        await create_durable_rag_job_and_wake_worker(
            self,
            job_type=DOCUMENT_UPLOAD_JOB_TYPE,
            conv_id=conv_id,
            user_id=user_id,
            document_id=doc_id,
            task_id=task_id,
            payload=queue_payload,
            spool_path=temp_file,
            logger=logger,
        )
    except RECOVERABLE_EXCEPTIONS:
        await delete_unqueued_rag_document(
            self,
            logger,
            doc_id=doc_id,
            conv_id=conv_id,
            operation=OPERATION,
        )
        raise
    record_worker_metric_counter(
        self.metrics,
        logger,
        MCP_RAG_COUNTER_DOCUMENTS_UPLOADS_QUEUED,
        operation=OPERATION,
        details={"doc_id": doc_id, "conv_id": conv_id},
    )
    record_worker_metric_gauge(
        self.metrics,
        logger,
        MCP_RAG_GAUGE_PROCESSING_QUEUE_SIZE,
        operation=OPERATION,
        details={"doc_id": doc_id, "conv_id": conv_id},
        value=self.processing_queue.qsize(),
    )
    await record_knowledge_prompt_event_and_publish(
        database_knowledge_prompt_state=self.database_knowledge_prompt_state,
        event_bus=self.event_bus,
        logger=logger,
        conv_id=conv_id,
        user_id=user_id,
        event_type="documents_added",
        document_names=(filename,),
        document_count=1,
        details={"document_id": doc_id, "source_type": "upload", "task_id": task_id},
        operation="mcp.worker.queue_upload.knowledge_prompt_event",
    )
