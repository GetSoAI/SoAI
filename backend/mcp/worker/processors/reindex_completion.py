"""SoAI - Reindex completion metadata and events [backend/mcp/worker/processors/reindex_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.errors.exceptions import ValidationError
from core.validation.coercion import coerce_int
from mcp.worker.processors.reindex_terminal_events import (
    ReindexTerminalEventContext,
    record_reindex_completed_event,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "ReindexCollectionActivationResult",
    "activate_reindex_collection",
    "complete_reindex_task",
)


@dataclass(frozen=True, slots=True)
class ReindexCollectionActivationResult:
    payload: JSONDict
    cancellation_requested: bool


async def activate_reindex_collection(
    worker: MCPWorkerProtocol,
    task_id: str,
    conv_id: str,
    embedding_model: str,
    embedding_dimensions: JSONValue,
    document_count: int,
    total_chunks: int,
    *,
    collection_name: str,
) -> ReindexCollectionActivationResult:
    await worker.send_progress(task_id, 90, "Updating collection metadata...")
    doc_count = max(0, int(document_count))
    metadata: JSONDict = {
        "effective_model": embedding_model,
    }
    dims_value = coerce_int(embedding_dimensions) or 0
    if dims_value <= 0:
        raise ValidationError(
            f"Invalid embedding dimensions for reindex metadata: {embedding_dimensions!r}",
        )
    activation_task = asyncio.create_task(
        worker.database_files.activate_rag_collection(
            collection_id=conv_id,
            conv_id=conv_id,
            collection_name=collection_name,
            embedding_model=embedding_model,
            embedding_dimensions=dims_value,
            document_count=doc_count,
            chunk_count=total_chunks,
            metadata=metadata,
        ),
        name="mcp.worker.reindex.activate_collection",
    )
    cancellation_requested = False
    try:
        await asyncio.shield(activation_task)
    except asyncio.CancelledError:
        cancellation_requested = True
        await uncancel_and_wait(activation_task)
    return ReindexCollectionActivationResult(
        payload={
            "conv_id": conv_id,
            "embedding_model": embedding_model,
            "embedding_dimensions": dims_value,
            "document_count": doc_count,
            "chunk_count": total_chunks,
        },
        cancellation_requested=cancellation_requested,
    )


async def complete_reindex_task(
    worker: MCPWorkerProtocol,
    task_id: str,
    conv_id: str,
    document_count: int,
    result: JSONDict,
    *,
    user_id: int,
    logger: LoggerProtocol,
) -> None:
    event_context = ReindexTerminalEventContext(conv_id, user_id, task_id, document_count)
    await record_reindex_completed_event(
        worker,
        logger=logger,
        context=event_context,
    )
    await worker.finalize_knowledge_attachment_task(
        task_id=task_id,
        processing_state="ready",
        terminal_item_status="completed",
        error_message=None,
    )
    await worker.complete_task(
        task_id,
        result=result,
        message="Reindex completed",
    )
