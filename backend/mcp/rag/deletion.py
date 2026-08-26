"""SoAI - MCP RAG document deletion operations [backend/mcp/rag/deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import uuid
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ServiceUnavailableError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_rag import MCP_RAG_COUNTER_DOCUMENTS_DELETIONS
from mcp.rag.indexing.sqlite_fts import SQLiteFTS5BM25Index
from mcp.rag.knowledge_prompt_events import record_knowledge_prompt_event_and_publish
from mcp.rag.maintenance_locks import (
    acquire_rag_maintenance_lease,
    release_rag_maintenance_lease,
    renew_rag_maintenance_lease,
)
from mcp.storage.chroma_naming import collection_prefix_from_conv_id
from mcp.storage.sparse_index import (
    ensure_sqlite_sparse_index_ready,
    get_sparse_settings,
    sqlite_sparse_index_path,
)
from mcp.worker.knowledge_attachment_events import (
    publish_worker_knowledge_attachment_summaries_noncritical,
)

if TYPE_CHECKING:
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "delete_all_documents",
    "delete_document",
)

LOGGER_NAME = "SoAI.mcp.rag.deletion"
OPERATION_MCP_RAG_DELETE_ALL_DOCUMENTS_DELETE_COLLECTION = (
    "mcp.rag.delete_all_documents.delete_collection"
)
OPERATION_MCP_RAG_DELETE_DOCUMENT_SPARSE_INDEX_REMOVE = (
    "mcp.rag.delete_document.sparse_index.remove"
)
OPERATION_MCP_RAG_DELETE_DOCUMENT_SPARSE_INDEX_UNLINK = (
    "mcp.rag.delete_document.sparse_index.unlink"
)
OPERATION_MCP_RAG_DELETE_DOCUMENT_LINKED_KNOWLEDGE_EVENT = (
    "mcp.rag.delete_document.linked_knowledge_event"
)
OPERATION_MCP_RAG_DELETE_ALL_DOCUMENTS_LINKED_KNOWLEDGE_EVENT = (
    "mcp.rag.delete_all_documents.linked_knowledge_event"
)


async def delete_document(self: MCPRAGInternalProtocol, conv_id: str, document_id: str) -> bool:
    logger = get_logger(LOGGER_NAME)
    document_before_delete = await self.database_files.get_rag_document_by_id(document_id)
    if document_before_delete is None:
        return False
    chunks = await self.database_files.get_rag_chunks_for_document_cleanup(document_id)
    chunk_ids: list[str] = []
    if isinstance(chunks, list):
        for row in chunks:
            if not isinstance(row, dict):
                continue
            chunk_id = row.get("id")
            if isinstance(chunk_id, str) and chunk_id:
                chunk_ids.append(chunk_id)

    chroma_lock = await self.storage.get_chroma_rw_lock(conv_id)
    async with chroma_lock:
        collection_name = await self.storage.chroma.resolve_active_collection_name(conv_id)
        delete_timeout = self.storage.config.get_int("TOOLS.RAG.CHROMA_DELETE_TIMEOUT_SEC")
        await self.storage.chroma.delete(
            conv_id=conv_id,
            collection_name=collection_name,
            ids=None,
            where={"document_id": document_id},
            timeout_sec=float(max(1, int(delete_timeout))),
        )
    deleted, linked_summaries = await self.database_files.delete_rag_document(
        document_id,
        conv_id,
    )
    if not deleted:
        logger.warning(
            "Deleted RAG vectors for document %s but DB delete was not confirmed; treating delete as failed.",
            document_id,
        )
        return False
    await publish_worker_knowledge_attachment_summaries_noncritical(
        self.event_bus,
        summaries=linked_summaries,
        operation=OPERATION_MCP_RAG_DELETE_DOCUMENT_LINKED_KNOWLEDGE_EVENT,
    )
    if chunk_ids:
        try:
            settings = await get_sparse_settings(self.storage, conv_id)
            index = SQLiteFTS5BM25Index(
                db_path=sqlite_sparse_index_path(self.storage, conv_id),
                tokenizer=settings["tokenizer"],
                stopwords_mode=settings["stopwords"],
            )
            if os.path.exists(index.db_path):
                await ensure_sqlite_sparse_index_ready(self.storage, conv_id, index)
                lock = await self.storage.get_sparse_index_lock(conv_id)
                async with lock:
                    await asyncio.to_thread(index.remove_documents, chunk_ids)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to remove sparse index documents; forcing rebuild on demand (non-critical).",
                operation=OPERATION_MCP_RAG_DELETE_DOCUMENT_SPARSE_INDEX_REMOVE,
                details={"conv_id": conv_id, "document_id": document_id},
                level="warning",
            )
            try:
                lock = await self.storage.get_sparse_index_lock(conv_id)
                async with lock:
                    sparse_index_file_path = sqlite_sparse_index_path(self.storage, conv_id)
                    os.unlink(sparse_index_file_path)
            except FileNotFoundError:
                logger.debug(
                    "Sparse index file already removed after deletion: conv_id=%s document_id=%s",
                    conv_id,
                    document_id,
                )
            except OSError as unlink_error:
                log_exception(
                    logger,
                    unlink_error,
                    message="Failed to remove sparse index file after deletion; stale results possible until rebuild.",
                    operation=OPERATION_MCP_RAG_DELETE_DOCUMENT_SPARSE_INDEX_UNLINK,
                    details={"conv_id": conv_id, "document_id": document_id},
                    level="warning",
                )
    if self.metrics is not None:
        self.metrics.increment_counter(*MCP_RAG_COUNTER_DOCUMENTS_DELETIONS)
    if document_before_delete is not None:
        filename = str(document_before_delete.get("filename") or document_id)
        user_id_value = document_before_delete.get("user_id")
        user_id = user_id_value if isinstance(user_id_value, int) else 0
        if user_id > 0:
            await record_knowledge_prompt_event_and_publish(
                database_knowledge_prompt_state=self.database_knowledge_prompt_state,
                event_bus=self.event_bus,
                logger=logger,
                conv_id=conv_id,
                user_id=user_id,
                event_type="documents_removed",
                document_names=(filename,),
                document_count=1,
                details={"document_id": document_id},
                operation="mcp.rag.delete_document.knowledge_prompt_event",
            )
    return True


async def delete_all_documents(self: MCPRAGInternalProtocol, conv_id: str) -> int:
    logger = get_logger(LOGGER_NAME)
    maintenance_lease_token = await acquire_rag_maintenance_lease(
        database_files=self.database_files,
        config=self.config,
        conv_id=conv_id,
        lock_type="delete_all",
        owner_task_id=f"delete_all:{uuid.uuid4().hex}",
        lease_owner="rag-delete-all",
        unavailable_message=f"RAG maintenance already in progress for conversation {conv_id}",
    )
    try:
        documents_before_delete = await self.database_files.get_rag_documents_for_conversation(
            conv_id,
            limit=20,
        )
        chroma_lock = await self.storage.get_chroma_rw_lock(conv_id)
        async with chroma_lock:
            delete_timeout = self.storage.config.get_int("TOOLS.RAG.CHROMA_DELETE_TIMEOUT_SEC")
            prefix = collection_prefix_from_conv_id(conv_id)
            all_names = await self.storage.chroma.list_collections_for_conv(
                conv_id=conv_id,
                timeout_sec=float(max(1, int(delete_timeout))),
            )
            target_names = [
                name for name in all_names if isinstance(name, str) and name.startswith(prefix)
            ]
            if not target_names:
                target_names = [await self.storage.chroma.resolve_active_collection_name(conv_id)]
            failures: list[str] = []
            for name in target_names:
                try:
                    await self.storage.chroma.delete_collection(
                        conv_id=conv_id,
                        collection_name=name,
                        timeout_sec=float(max(1, int(delete_timeout))),
                    )
                except RECOVERABLE_EXCEPTIONS as exception:
                    failures.append(str(name))
                    log_exception(
                        logger,
                        exception,
                        message="Failed to delete Chroma collection during delete_all_documents.",
                        operation=OPERATION_MCP_RAG_DELETE_ALL_DOCUMENTS_DELETE_COLLECTION,
                        details={"conv_id": conv_id, "collection_name": str(name)},
                        level="warning",
                    )
            if failures:
                raise ServiceUnavailableError(
                    "Failed to delete one or more vector collections; aborting DB cleanup.",
                    operation="mcp.rag.delete_all_documents",
                    details={
                        "conv_id": conv_id,
                        "failed_count": len(failures),
                        "failed_collections_sample": failures[:10],
                    },
                )
        await renew_rag_maintenance_lease(
            database_files=self.database_files,
            config=self.config,
            conv_id=conv_id,
            lease_token=maintenance_lease_token,
            expired_message=f"RAG maintenance lock expired for conversation {conv_id}",
        )
        sparse_lock = await self.storage.get_sparse_index_lock(conv_id)
        async with sparse_lock:
            try:
                sparse_index_file_path = sqlite_sparse_index_path(self.storage, conv_id)
                os.unlink(sparse_index_file_path)
            except FileNotFoundError:
                logger.debug("Sparse index file missing for %s; nothing to delete.", conv_id)
            except OSError as error:
                logger.debug("Failed to remove sparse index for %s: %s", conv_id, str(error))
        deleted_count, linked_summaries = (
            await self.database_files.delete_rag_documents_for_conversation(conv_id)
        )
        await publish_worker_knowledge_attachment_summaries_noncritical(
            self.event_bus,
            summaries=linked_summaries,
            operation=OPERATION_MCP_RAG_DELETE_ALL_DOCUMENTS_LINKED_KNOWLEDGE_EVENT,
        )
        await self.database_files.delete_rag_collection_metadata_for_conversation(conv_id)
        if deleted_count and self.metrics is not None:
            self.metrics.increment_counter(
                *MCP_RAG_COUNTER_DOCUMENTS_DELETIONS,
                value=deleted_count,
            )
        if deleted_count:
            user_id = 0
            document_names: list[str] = []
            for row in documents_before_delete:
                if user_id <= 0:
                    user_id_value = row.get("user_id")
                    user_id = user_id_value if isinstance(user_id_value, int) else 0
                filename = str(row.get("filename") or "").strip()
                if filename:
                    document_names.append(filename)
            if user_id > 0:
                await record_knowledge_prompt_event_and_publish(
                    database_knowledge_prompt_state=self.database_knowledge_prompt_state,
                    event_bus=self.event_bus,
                    logger=logger,
                    conv_id=conv_id,
                    user_id=user_id,
                    event_type="documents_removed",
                    document_names=tuple(document_names),
                    document_count=deleted_count,
                    details={"deleted_count": deleted_count},
                    operation="mcp.rag.delete_all_documents.knowledge_prompt_event",
                )
        return deleted_count
    finally:
        await release_rag_maintenance_lease(
            database_files=self.database_files,
            conv_id=conv_id,
            lease_token=maintenance_lease_token,
        )
