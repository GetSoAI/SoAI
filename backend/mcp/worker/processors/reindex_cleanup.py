"""SoAI - Reindex task cancellation and cleanup flows [backend/mcp/worker/processors/reindex_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from mcp.worker.processors.reindex_terminal_events import (
    ReindexTerminalEventContext,
    record_reindex_cancelled_event,
)

if TYPE_CHECKING:
    from core.concurrency.locks import AsyncRWLock
    from core.logging.protocols import LoggerProtocol
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "cleanup_failed_reindex",
    "cleanup_old_reindex_collections",
    "finalize_reindex_cancellation",
    "handle_reindex_cancellation",
    "handle_reindex_error_cleanup",
)

LOGGER_NAME = "SoAI.mcp.worker.reindex_cleanup"
OPERATION_MCP_WORKER_PROCESS_REINDEX_CLEANUP = "mcp.worker.process_reindex.cleanup"
OPERATION_MCP_WORKER_PROCESS_REINDEX_CLEANUP_OLD_COLLECTIONS = (
    "mcp.worker.process_reindex.cleanup_old_collections"
)
OPERATION_MCP_WORKER_PROCESS_REINDEX_CLEANUP_OLD_COLLECTIONS_LIST = (
    "mcp.worker.process_reindex.cleanup_old_collections.list"
)
OPERATION_MCP_WORKER_PROCESS_REINDEX_SHUTDOWN = "mcp.worker.process_reindex.shutdown"


async def handle_reindex_cancellation(
    worker: MCPWorkerProtocol,
    task_id: str,
    *,
    cancelled_by_user: bool,
    reason: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        if cancelled_by_user:
            await worker.cancel_task(task_id, reason)
            return
        task = await worker.task_registry.get(task_id)
        if not task or task.status != TaskStatus.CANCELLED:
            await worker.fail_task(task_id, "Worker shutdown")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to update cancellation state during reindex shutdown (non-critical).",
            operation=OPERATION_MCP_WORKER_PROCESS_REINDEX_SHUTDOWN,
            details={"task_id": task_id},
            level="debug",
        )


async def handle_reindex_error_cleanup(
    worker: MCPWorkerProtocol,
    task_id: str,
    conv_id: str,
    temp_collection_name: str,
    error: BaseException,
    chroma_lock: AsyncRWLock | None,
) -> None:
    try:
        await worker.fail_task(task_id, str(error))
    finally:
        await uncancel_then_cleanup(
            cleanup_failed_reindex(
                worker,
                conv_id=conv_id,
                collection_name=temp_collection_name,
                task_id=task_id,
                chroma_lock=chroma_lock,
            ),
        )


async def finalize_reindex_cancellation(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    task_id: str,
    conv_id: str,
    user_id: int,
    document_count: int,
    reason: str,
    cancelled_by_user: bool,
    collection_metadata_activated: bool,
    collection_name: str,
    chroma_lock: AsyncRWLock | None,
) -> None:
    await handle_reindex_cancellation(
        worker,
        task_id,
        cancelled_by_user=cancelled_by_user,
        reason=reason,
    )
    event_context = ReindexTerminalEventContext(conv_id, user_id, task_id, document_count)
    await record_reindex_cancelled_event(
        worker,
        logger=logger,
        context=event_context,
        reason=reason,
    )
    await worker.finalize_knowledge_attachment_task(
        task_id=task_id,
        processing_state="cancelled",
        terminal_item_status="cancelled",
        error_message=reason,
    )
    if not collection_metadata_activated:
        await cleanup_failed_reindex(
            worker,
            conv_id=conv_id,
            collection_name=collection_name,
            task_id=task_id,
            chroma_lock=chroma_lock,
        )


async def cleanup_failed_reindex(
    worker: MCPWorkerProtocol,
    *,
    conv_id: str,
    collection_name: str,
    task_id: str,
    chroma_lock: AsyncRWLock | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    name = str(collection_name or "").strip()
    if not name:
        return
    try:
        if chroma_lock is None:
            await worker.storage.chroma.delete_collection(
                conv_id=conv_id or "unknown",
                collection_name=name,
                timeout_sec=30.0,
            )
        else:
            async with chroma_lock.write_lock():
                await worker.storage.chroma.delete_collection(
                    conv_id=conv_id or "unknown",
                    collection_name=name,
                    timeout_sec=30.0,
                )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to cleanup reindex collection.",
            operation=OPERATION_MCP_WORKER_PROCESS_REINDEX_CLEANUP,
            details={"task_id": task_id, "collection_name": name},
            level="error",
        )
        raise


async def cleanup_old_reindex_collections(
    worker: MCPWorkerProtocol,
    *,
    conv_id: str,
    keep_collection_name: str,
    prefix: str,
    task_id: str,
    old_collection_name: str,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    cleanup_complete = True
    all_names: list[str] = []
    try:
        all_names = await worker.storage.chroma.list_collections_for_conv(
            conv_id=conv_id,
            timeout_sec=30.0,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        cleanup_complete = False
        log_exception(
            logger,
            exception,
            message="Failed to list collections for cleanup after reindex.",
            operation=OPERATION_MCP_WORKER_PROCESS_REINDEX_CLEANUP_OLD_COLLECTIONS_LIST,
            details={"task_id": task_id},
            level="error",
        )
    target_names = [
        name
        for name in all_names
        if isinstance(name, str) and name.startswith(prefix) and name != keep_collection_name
    ]
    if old_collection_name and old_collection_name != keep_collection_name:
        target_names.append(old_collection_name)
    seen: set[str] = set()
    for name in target_names:
        if name in seen:
            continue
        seen.add(name)
        try:
            await worker.storage.chroma.delete_collection(
                conv_id=conv_id,
                collection_name=name,
                timeout_sec=30.0,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            cleanup_complete = False
            log_exception(
                logger,
                exception,
                message="Failed to cleanup old collection after reindex.",
                operation=OPERATION_MCP_WORKER_PROCESS_REINDEX_CLEANUP_OLD_COLLECTIONS,
                details={"task_id": task_id, "collection_name": name},
                level="error",
            )
    return cleanup_complete
