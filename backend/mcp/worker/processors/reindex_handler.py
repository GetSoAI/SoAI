"""SoAI - RAG reindex processing and lifecycle orchestration [backend/mcp/worker/processors/reindex_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.validation.coercion import coerce_int
from core.validation.strings import coerce_optional_trimmed_str
from mcp.rag.maintenance_locks import (
    acquire_rag_maintenance_lease,
    release_rag_maintenance_lease,
    renew_rag_maintenance_lease,
)
from mcp.storage.chroma_collection_reservation import reserve_chroma_collection_metadata
from mcp.storage.chroma_naming import (
    build_reindex_collection_name,
    collection_prefix_from_conv_id,
)
from mcp.worker.processing.durable_job_payloads import lease_identity_from_job_payload
from mcp.worker.processing.durable_job_runtime import renew_durable_processing_lease
from mcp.worker.processors.reindex_cleanup import (
    cleanup_old_reindex_collections,
    finalize_reindex_cancellation,
    handle_reindex_error_cleanup,
)
from mcp.worker.processors.reindex_completion import (
    activate_reindex_collection,
    complete_reindex_task,
)
from mcp.worker.processors.reindex_document_loop import (
    ReindexDocumentLoopConfig,
    process_documents_for_reindex,
)
from mcp.worker.processors.reindex_task_status import update_reindex_initial_status
from mcp.worker.processors.reindex_terminal_events import (
    ReindexTerminalEventContext,
    record_reindex_failed_event,
)

if TYPE_CHECKING:
    from core.concurrency.locks import AsyncRWLock
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("process_reindex",)

LOGGER_NAME = "SoAI.mcp.worker.reindex_handler"
OPERATION_MCP_WORKER_PROCESS_REINDEX = "mcp.worker.process_reindex"


async def process_reindex(
    self: MCPWorkerProtocol,
    job: JSONDict,
    task_id: str,
    token: CancellationTokenProtocol | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    conv_id = str(job.get("conv_id") or "").strip()
    embedding_model_value = job.get("embedding_model")
    embedding_model = coerce_optional_trimmed_str(
        embedding_model_value if isinstance(embedding_model_value, str) else None,
    )
    embedding_dimensions = job.get("embedding_dimensions")
    lock_key = str(job.get("lock_key") or conv_id)
    user_id = coerce_int(job.get("user_id")) or 0
    document_count = coerce_int(job.get("document_count")) or 0
    job_id, lease_token = lease_identity_from_job_payload(job)
    if not conv_id:
        try:
            await self.fail_task(task_id, "Missing conv_id for reindex job")
        finally:
            await self.reindex_locks.release(lock_key)
        return
    if embedding_model is None:
        try:
            await self.fail_task(task_id, "Missing embedding_model for reindex job")
        finally:
            await self.reindex_locks.release(lock_key)
        return
    new_collection_name = ""
    chroma_lock: AsyncRWLock | None = None
    collection_metadata_activated = False
    maintenance_lease_token: str | None = None
    try:
        maintenance_lease_token = await acquire_rag_maintenance_lease(
            database_files=self.database_files,
            config=self.config,
            conv_id=conv_id,
            lock_type="reindex",
            owner_task_id=task_id,
            lease_owner="rag-reindex",
            unavailable_message=f"Reindex already in progress for conversation {conv_id}",
        )
        await update_reindex_initial_status(self, task_id)
        new_collection_name = build_reindex_collection_name(conv_id, task_id)
        chroma_lock = await self.storage.get_chroma_rw_lock(conv_id)
        await self.send_progress(task_id, 5, "Creating temporary vector collection...")
        with reserve_chroma_collection_metadata(
            self.storage.storage_manager,
            chroma_path=self.storage.chroma_path,
            operation="mcp.worker.reindex.ensure_collection",
            details={
                "purpose": "rag_reindex_chroma_collection_metadata",
                "conv_id": conv_id,
                "collection_name": new_collection_name,
                "task_id": task_id,
            },
        ):
            await self.storage.chroma.ensure_collection(
                conv_id=conv_id,
                collection_name=new_collection_name,
                embedding_model=embedding_model,
                effective_model=embedding_model,
                timeout_sec=30.0,
            )
        loop_config = ReindexDocumentLoopConfig(
            conv_id=conv_id,
            embedding_model=embedding_model,
            embedding_dimensions=(
                coerce_int(embedding_dimensions) or 0 if embedding_dimensions is not None else None
            ),
            collection_name=new_collection_name,
            user_id=user_id,
            task_id=task_id,
            document_count=document_count,
            job_id=job_id,
            lease_token=lease_token,
            maintenance_lease_token=maintenance_lease_token,
        )
        result = await process_documents_for_reindex(self, loop_config, token=token)
        total_chunks = result.total_chunks
        if total_chunks <= 0:
            raise ValidationError(f"No chunks found to reindex for conversation {conv_id}")
        await self.check_cancellation(task_id, "reindex-swap", token=token)
        if job_id and lease_token:
            await renew_durable_processing_lease(self, job_id=job_id, lease_token=lease_token)
        await renew_rag_maintenance_lease(
            database_files=self.database_files,
            config=self.config,
            conv_id=conv_id,
            lease_token=maintenance_lease_token,
            expired_message=f"Reindex maintenance lock expired for conversation {conv_id}",
        )
        await self.send_progress(task_id, 80, "Activating new vector collection...")
        async with chroma_lock.write_lock():
            old_collection_name = await self.storage.chroma.resolve_active_collection_name(conv_id)
            activation_result = await activate_reindex_collection(
                self,
                task_id,
                conv_id,
                embedding_model,
                embedding_dimensions,
                document_count,
                total_chunks,
                collection_name=new_collection_name,
            )
            collection_metadata_activated = True
            if activation_result.cancellation_requested:
                raise asyncio.CancelledError
            completion_payload = activation_result.payload
            cleanup_complete = await cleanup_old_reindex_collections(
                self,
                conv_id=conv_id,
                keep_collection_name=new_collection_name,
                prefix=collection_prefix_from_conv_id(conv_id),
                task_id=task_id,
                old_collection_name=old_collection_name,
            )
            if not cleanup_complete:
                completion_payload["old_collection_cleanup_complete"] = False
        await complete_reindex_task(
            self,
            task_id,
            conv_id,
            document_count,
            completion_payload,
            user_id=user_id,
            logger=logger,
        )
    except TaskCancelledError as error:
        reason = error.reason
        await finalize_reindex_cancellation(
            self,
            logger=logger,
            task_id=task_id,
            conv_id=conv_id,
            user_id=user_id,
            document_count=document_count,
            reason=reason,
            cancelled_by_user=True,
            collection_metadata_activated=collection_metadata_activated,
            collection_name=new_collection_name,
            chroma_lock=chroma_lock,
        )
    except asyncio.CancelledError:
        cancelled_by_user = bool(token is not None and token.thread_event.is_set())
        reason = (
            token.cancellation_reason.strip()
            if token is not None
            and isinstance(token.cancellation_reason, str)
            and token.cancellation_reason.strip()
            else "Cancelled by user"
        )
        await finalize_reindex_cancellation(
            self,
            logger=logger,
            task_id=task_id,
            conv_id=conv_id,
            user_id=user_id,
            document_count=document_count,
            reason=reason,
            cancelled_by_user=cancelled_by_user,
            collection_metadata_activated=collection_metadata_activated,
            collection_name=new_collection_name,
            chroma_lock=chroma_lock,
        )
        raise
    except RECOVERABLE_EXCEPTIONS as error:
        log_exception(
            logger,
            error,
            message="Reindex failed",
            operation=OPERATION_MCP_WORKER_PROCESS_REINDEX,
            details={"conv_id": conv_id, "task_id": task_id},
        )
        if collection_metadata_activated:
            await self.fail_task(task_id, str(error))
        else:
            await handle_reindex_error_cleanup(
                self,
                task_id,
                conv_id,
                new_collection_name,
                error,
                chroma_lock,
            )
        event_context = ReindexTerminalEventContext(conv_id, user_id, task_id, document_count)
        await record_reindex_failed_event(
            self,
            logger=logger,
            context=event_context,
            error_message=str(error),
        )
        await self.finalize_knowledge_attachment_task(
            task_id=task_id,
            processing_state="error",
            terminal_item_status="error",
            error_message=str(error),
        )
    finally:
        try:
            await release_rag_maintenance_lease(
                database_files=self.database_files,
                conv_id=conv_id,
                lease_token=maintenance_lease_token,
            )
        finally:
            await self.reindex_locks.release(lock_key)
