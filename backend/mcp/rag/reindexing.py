"""SoAI - MCP RAG reindexing operations [backend/mcp/rag/reindexing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_rag import MCP_RAG_GAUGE_PROCESSING_QUEUE_SIZE
from core.tasks.enums import TaskStatus
from core.tasks.task_cancellation import cancel
from core.tasks.type_catalog import TASK_TYPE_RAG_REINDEX
from core.validation.strings import coerce_optional_trimmed_str
from mcp.progress_reporting import create_rag_task
from mcp.rag.knowledge_prompt_events import record_knowledge_prompt_event_and_publish
from mcp.rag.reindex_cleanup_errors import REINDEX_CLEANUP_EXCEPTIONS
from mcp.rag.reindex_knowledge_attachment_lifecycle import (
    create_reindex_knowledge_attachment,
    finalize_unqueued_reindex_knowledge_attachment,
)
from mcp.storage import sparse_index
from mcp.storage.embedding_model import validate_and_resolve_embedding_model
from mcp.worker.durable_enqueue import create_durable_rag_job_and_wake_worker
from mcp.worker.metrics_reporting import (
    record_worker_metric_gauge,
)
from mcp.worker.processing.job_types import REINDEX_JOB_TYPE

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "get_collection_metadata",
    "rebuild_sparse_index",
    "reindex_conversation",
)

LOGGER_NAME = "SoAI.mcp.rag.reindexing"
OPERATION_REINDEX_QUEUE = "mcp.rag.reindexing.queue"


async def _cancel_unqueued_reindex_task(
    self: MCPRAGInternalProtocol,
    *,
    task_id: str,
    reason: str,
    logger: LoggerProtocol,
) -> None:
    try:
        await cancel(self.task_registry, task_id, reason=reason)
    except REINDEX_CLEANUP_EXCEPTIONS as cleanup_exception:
        logger.warning(
            "Failed to cancel unqueued RAG reindex task %s: %s",
            task_id,
            str(cleanup_exception),
        )


async def reindex_conversation(
    self: MCPRAGInternalProtocol,
    conv_id: str,
    user_id: int,
    model_id: str,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        raise ValidationError("model_id must be a non-empty string")
    validated_model, embedding_dimensions = await validate_and_resolve_embedding_model(
        self.storage,
        normalized_model_id,
    )
    if embedding_dimensions <= 0:
        raise ValidationError(
            f"Invalid embedding dimensions detected for model {validated_model!r}: {embedding_dimensions}",
        )
    lock_acquired = await self.worker.reindex_locks.acquire(conv_id)
    if not lock_acquired:
        raise ValidationError(f"Reindex already in progress for conversation {conv_id}")
    enqueued = False
    task_id: str | None = None
    knowledge_summary_created = False
    updated_summary: JSONDict | None = None
    try:
        counts = await self.database_files.get_rag_counts_for_conversation(conv_id)
        completed_count_value = counts.get("completed") if isinstance(counts, dict) else 0
        completed_count = completed_count_value if isinstance(completed_count_value, int) else 0
        if completed_count <= 0:
            raise ValidationError(f"No RAG documents found for conversation {conv_id}")
        sample_documents = await self.database_files.get_rag_documents_for_conversation(
            conv_id,
            limit=20,
        )
        task = await create_rag_task(
            self.task_registry,
            task_type=TASK_TYPE_RAG_REINDEX,
            user_id=user_id,
            conv_id=conv_id,
            status=TaskStatus.PENDING,
            progress_total=100,
            metadata={
                "conv_id": conv_id,
                "embedding_model": validated_model,
            },
        )
        task_id = task.task_id
        updated_summary = await create_reindex_knowledge_attachment(
            self,
            conv_id=conv_id,
            user_id=user_id,
            task_id=task_id,
            embedding_model=validated_model,
        )
        knowledge_summary_created = True
        queue_item: JSONDict = {
            "type": REINDEX_JOB_TYPE,
            "task_id": task_id,
            "conv_id": conv_id,
            "embedding_model": validated_model,
            "embedding_dimensions": embedding_dimensions,
            "document_count": completed_count,
            "user_id": user_id,
            "lock_key": conv_id,
        }
        await create_durable_rag_job_and_wake_worker(
            self.worker,
            job_type=REINDEX_JOB_TYPE,
            conv_id=conv_id,
            user_id=user_id,
            document_id=None,
            task_id=task_id,
            payload=queue_item,
            spool_path=None,
            logger=logger,
        )
        enqueued = True
        record_worker_metric_gauge(
            self.worker.metrics,
            logger,
            MCP_RAG_GAUGE_PROCESSING_QUEUE_SIZE,
            operation=OPERATION_REINDEX_QUEUE,
            details={"task_id": task_id, "conv_id": conv_id},
            value=self.worker.processing_queue.qsize(),
        )
        document_names = tuple(
            str(doc.get("filename") or "").strip()
            for doc in sample_documents
            if str(doc.get("filename") or "").strip()
        )
        await record_knowledge_prompt_event_and_publish(
            database_knowledge_prompt_state=self.database_knowledge_prompt_state,
            event_bus=self.event_bus,
            logger=logger,
            conv_id=conv_id,
            user_id=user_id,
            event_type="knowledge_reindex_queued",
            document_names=tuple(name for name in document_names if name),
            document_count=completed_count,
            details={"task_id": task_id, "embedding_model": validated_model},
            operation="mcp.rag.reindexing.knowledge_prompt_event",
        )
    except (
        SoAIError,
        RuntimeError,
        OSError,
        TypeError,
        ValueError,
    ) as exception:
        if task_id is not None and not enqueued:
            await _cancel_unqueued_reindex_task(
                self,
                task_id=task_id,
                reason=str(exception) or "RAG reindex was not queued.",
                logger=logger,
            )
            if knowledge_summary_created:
                await finalize_unqueued_reindex_knowledge_attachment(
                    self,
                    task_id=task_id,
                    error_message=str(exception) or "RAG reindex was not queued.",
                    logger=logger,
                )
        raise
    finally:
        if not enqueued:
            await uncancel_then_cleanup(self.worker.reindex_locks.release(conv_id))
    if not task_id or updated_summary is None:
        raise StateError("Reindex task creation failed.")
    return {"task_id": task_id, "knowledge_attachment": updated_summary}


async def get_collection_metadata(self: MCPRAGInternalProtocol, conv_id: str) -> JSONDict:
    rw_lock = await self.storage.get_chroma_rw_lock(conv_id)
    async with rw_lock.read_lock():
        collection_name = await self.storage.chroma.resolve_active_collection_name(conv_id)
        query_timeout = self.storage.config.get_int("TOOLS.RAG.CHROMA_QUERY_TIMEOUT_SEC")
        count = await self.storage.chroma.count(
            conv_id=conv_id,
            collection_name=collection_name,
            timeout_sec=float(max(1, int(query_timeout))),
        )
        metadata = await self.storage.database_files.get_rag_collection_metadata(conv_id)
        embedding_model_value = (
            metadata.get("embedding_model") if isinstance(metadata, dict) else None
        )
        embedding_model = coerce_optional_trimmed_str(
            embedding_model_value if isinstance(embedding_model_value, str) else None,
        )
        return {
            "collection_name": collection_name,
            "conv_id": conv_id,
            "embedding_model": embedding_model,
            "count": int(count),
            "exists": count > 0,
        }


async def rebuild_sparse_index(self: MCPRAGInternalProtocol, conv_id: str) -> None:
    await sparse_index.rebuild_sparse_index(self.storage, conv_id)
