"""SoAI - MCP progress utilities and embedding-event helpers [backend/mcp/progress_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.events.types_models_requests import EmbeddingRequestReceived
from core.files.database_types import RAGDocumentRecord
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_context_trace_id
from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import build_soai_id
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.tasks.type_catalog import TaskTypeId
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.files.protocols import DatabaseFilesProtocol
    from core.types.json import JSONDict

__all__ = (
    "calculate_scaled_progress",
    "cleanup_document_entry",
    "cleanup_rag_document_entry",
    "cleanup_task_registry_entry",
    "compute_progress_update",
    "create_rag_task",
    "publish_embedding_event",
    "require_rag_document_with_conv_id",
)

OPERATION_MCP_PROGRESS_REPORTING_PUBLISH_EMBEDDING_EVENT = (
    "mcp.progress_reporting.publish_embedding_event"
)


OPERATION_MCP_PROGRESS_REPORTING_CLEANUP_DOCUMENT_ENTRY = (
    "mcp.progress_reporting.cleanup_document_entry"
)
OPERATION_MCP_PROGRESS_REPORTING_CLEANUP_TASK_REGISTRY_ENTRY = (
    "mcp.progress_reporting.cleanup_task_registry_entry"
)


def calculate_scaled_progress(
    current: int,
    total: int | None,
    *,
    progress_start: int,
    progress_end: int,
) -> int:
    span = max(0, int(progress_end) - int(progress_start))
    ratio = current / total if total is not None and int(total) > 0 else 0.0
    scaled_percent = (
        int(progress_start) + int(min(1.0, max(0.0, ratio)) * span)
        if span > 0
        else int(progress_end)
    )
    return min(100, max(0, scaled_percent))


def compute_progress_update(
    *,
    current: int,
    total: int | None,
    progress_start: int,
    progress_end: int,
    last_reported_percent: int,
    last_reported_at: float,
    last_reported_bytes: int,
    now: float | None = None,
) -> tuple[int, bool, float]:
    timestamp = time.monotonic() if now is None else now
    scaled_percent = calculate_scaled_progress(
        current,
        total,
        progress_start=progress_start,
        progress_end=progress_end,
    )
    should_report = scaled_percent != last_reported_percent or (
        timestamp - last_reported_at >= 1.0 and current != last_reported_bytes
    )
    return scaled_percent, should_report, timestamp


async def cleanup_task_registry_entry(
    task_id: str,
    cleanup_action: Callable[[], Awaitable[None | bool]],
    *,
    logger: LoggerProtocol,
) -> None:
    try:
        await cleanup_action()
    except RECOVERABLE_EXCEPTIONS as cleanup_error:
        log_exception(
            logger,
            cleanup_error,
            message="Failed to cleanup task registry entry.",
            operation=OPERATION_MCP_PROGRESS_REPORTING_CLEANUP_TASK_REGISTRY_ENTRY,
            details={"task_id": task_id},
            level="warning",
        )


async def cleanup_document_entry(
    document_id: str,
    cleanup_action: Callable[[], Awaitable[None | bool]],
    *,
    logger: LoggerProtocol,
) -> None:
    try:
        await cleanup_action()
    except RECOVERABLE_EXCEPTIONS as cleanup_error:
        log_exception(
            logger,
            cleanup_error,
            message="Failed to cleanup DB document entry.",
            operation=OPERATION_MCP_PROGRESS_REPORTING_CLEANUP_DOCUMENT_ENTRY,
            details={"document_id": document_id},
            level="warning",
        )


async def cleanup_rag_document_entry(
    document_id: str,
    conv_id: str,
    database_files: DatabaseFilesProtocol,
    *,
    logger: LoggerProtocol,
) -> None:
    async def delete_document_entry() -> bool:
        deleted, _linked_summaries = await database_files.delete_rag_document(document_id, conv_id)
        return deleted

    await cleanup_document_entry(
        document_id,
        delete_document_entry,
        logger=logger,
    )


async def require_rag_document_with_conv_id(
    database_files: DatabaseFilesProtocol,
    document_id: str,
) -> tuple[RAGDocumentRecord, str]:
    doc = await database_files.get_rag_document_by_id(document_id)
    if not doc:
        raise MCPJSONRPCError(-32602, f"Document not found: {document_id}")
    doc_conv_id = doc.get("conv_id")
    if not isinstance(doc_conv_id, str) or not doc_conv_id:
        raise MCPJSONRPCError(-32603, f"Document has no conv_id: {document_id}")
    return doc, doc_conv_id


async def publish_embedding_event(
    *,
    event_bus: EventBusProtocol,
    task_registry: TaskRegistryProtocol,
    context: RequestContext,
    payload: JSONDict,
    reply_channel: asyncio.Queue[Event],
    task_id: str,
    required_capabilities: Sequence[str],
    logger: LoggerProtocol,
    operation: str,
    error_code: int,
    error_message: str,
    soai_error_code: int | None = None,
    soai_error_message: str | None = None,
    exception_types: tuple[type[BaseException], ...] = (SoAIError,),
) -> None:
    try:
        await event_bus.publish(
            EmbeddingRequestReceived(
                context=context,
                payload=payload,
                reply_channel=reply_channel,
                task_id=task_id,
                required_capabilities=tuple(required_capabilities),
            ),
        )
    except exception_types as exception:
        resolved_error_code = (
            soai_error_code
            if isinstance(exception, SoAIError) and soai_error_code is not None
            else error_code
        )
        resolved_error_message = (
            soai_error_message
            if isinstance(exception, SoAIError) and soai_error_message is not None
            else error_message
        )
        log_exception(
            logger,
            exception,
            message="Failed to publish embedding event.",
            trace_id=get_context_trace_id(context),
            operation=OPERATION_MCP_PROGRESS_REPORTING_PUBLISH_EMBEDDING_EVENT,
            details={"publish_operation": operation, "task_id": task_id},
        )
        await finalize(
            task_registry,
            task_id,
            TaskStatus.FAILED,
            error_code=resolved_error_code,
            error_message=resolved_error_message,
        )
        raise


async def create_rag_task(
    task_registry: TaskRegistryProtocol,
    *,
    task_type: TaskTypeId,
    user_id: int,
    conv_id: str,
    status: TaskStatus,
    progress_total: int,
    metadata: JSONDict | None = None,
) -> Task:
    return await create(
        task_registry,
        task_type=task_type,
        user_id=user_id,
        owner_id=conv_id,
        owner_type="conversation",
        cancellation_id=build_soai_id(("task", "mcp", "rag", conv_id, uuid.uuid4().hex[:12])),
        status=status,
        progress_total=progress_total,
        metadata=metadata,
    )
