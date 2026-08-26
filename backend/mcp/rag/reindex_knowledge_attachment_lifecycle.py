"""SoAI - RAG reindex knowledge attachment lifecycle [backend/mcp/rag/reindex_knowledge_attachment_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_constants import STAGED_ATTACHMENT_TTL_MS
from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol
from core.timing.epoch import epoch_ms
from core.validation.strings import coerce_optional_trimmed_str
from mcp.rag.reindex_cleanup_errors import REINDEX_CLEANUP_EXCEPTIONS
from mcp.worker.knowledge_attachment_events import (
    publish_worker_knowledge_attachment_changed_noncritical,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "create_reindex_knowledge_attachment",
    "finalize_unqueued_reindex_knowledge_attachment",
)


async def finalize_unqueued_reindex_knowledge_attachment(
    self: MCPRAGInternalProtocol,
    *,
    task_id: str,
    error_message: str,
    logger: LoggerProtocol,
) -> None:
    try:
        summary = (
            await (
                self.database_conversation_knowledge_attachments.finalize_knowledge_attachment_task(
                    task_id=task_id,
                    processing_state="error",
                    terminal_item_status="error",
                    error_message=error_message,
                )
            )
        )
        if summary is not None:
            await publish_worker_knowledge_attachment_changed_noncritical(
                self.event_bus,
                summary=summary,
                operation="mcp.rag.reindexing.unqueued_knowledge_event",
            )
    except REINDEX_CLEANUP_EXCEPTIONS as cleanup_exception:
        logger.warning(
            "Failed to finalize unqueued RAG reindex knowledge attachment %s: %s",
            task_id,
            str(cleanup_exception),
        )


async def create_reindex_knowledge_attachment(
    self: MCPRAGInternalProtocol,
    *,
    conv_id: str,
    user_id: int,
    task_id: str,
    embedding_model: str,
) -> JSONDict:
    created_at = epoch_ms()
    summary = await self.database_conversation_knowledge_attachments.ensure_knowledge_attachment(
        conv_id=conv_id,
        user_id=user_id,
        source_type="reindex",
        operation_type="reindexed",
        title=f"Reindex {embedding_model}",
        root_label=None,
        root_virtual_path=None,
        task_id=task_id,
        client_batch_id=None,
        created_at_ms=created_at,
        expires_at_ms=created_at + STAGED_ATTACHMENT_TTL_MS,
    )
    knowledge_attachment_id = coerce_optional_trimmed_str(
        (
            summary.get("knowledge_attachment_id")
            if isinstance(summary.get("knowledge_attachment_id"), str)
            else None
        ),
    )
    if knowledge_attachment_id is None:
        raise StateError("Reindex knowledge attachment id is invalid.")
    await publish_worker_knowledge_attachment_changed_noncritical(
        self.event_bus,
        summary=summary,
        operation="mcp.rag.reindexing.queued_knowledge_event",
    )
    return summary
