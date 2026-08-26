"""SoAI - RAG document status update publishing [backend/mcp/worker/rag_status_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.rag.job_operations import (
    RAGDocumentStatusJobUpdateRequest,
    RAGDocumentStatusUpdateRequest,
)
from mcp.worker.knowledge_attachment_events import (
    publish_worker_knowledge_attachment_changed_noncritical,
    publish_worker_knowledge_attachment_summaries_noncritical,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "publish_rag_document_status_update",
    "publish_rag_document_status_update_for_job",
)


async def _publish_status_side_effects(
    worker: MCPWorkerProtocol,
    *,
    linked_summaries: list[JSONDict],
    knowledge_summary: JSONDict | None,
    operation: str,
) -> None:
    await publish_worker_knowledge_attachment_summaries_noncritical(
        worker.event_bus,
        summaries=linked_summaries,
        operation=f"{operation}.linked_knowledge_event",
    )
    if knowledge_summary is not None:
        await publish_worker_knowledge_attachment_changed_noncritical(
            worker.event_bus,
            summary=knowledge_summary,
            operation=f"{operation}.knowledge_event",
        )


async def publish_rag_document_status_update(
    worker: MCPWorkerProtocol,
    request: RAGDocumentStatusUpdateRequest,
) -> None:
    linked_summaries, knowledge_summary = await worker.database_files.update_rag_document_status(
        request
    )
    await _publish_status_side_effects(
        worker,
        linked_summaries=linked_summaries,
        knowledge_summary=knowledge_summary,
        operation="mcp.worker.update_rag_document_status",
    )


async def publish_rag_document_status_update_for_job(
    worker: MCPWorkerProtocol,
    request: RAGDocumentStatusJobUpdateRequest,
) -> None:
    linked_summaries, knowledge_summary = (
        await worker.database_files.update_rag_document_status_for_job(request)
    )
    await _publish_status_side_effects(
        worker,
        linked_summaries=linked_summaries,
        knowledge_summary=knowledge_summary,
        operation="mcp.worker.update_rag_document_status_for_job",
    )
