"""SoAI - MCP worker Knowledge prompt event helpers [backend/mcp/worker/knowledge_prompt_recording.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.rag.knowledge_prompt_types import KnowledgePromptEventType
from core.validation.coercion import coerce_int
from mcp.rag.knowledge_prompt_events import record_knowledge_prompt_event_and_publish

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("record_document_knowledge_prompt_event", "record_worker_knowledge_prompt_event")


async def record_document_knowledge_prompt_event(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    job: JSONDict,
    document_id: str,
    conv_id: str,
    task_id: str,
    event_type: KnowledgePromptEventType,
    detail_message: str,
    operation: str,
) -> None:
    document = await worker.database_files.get_rag_document_by_id(document_id)
    filename = str(document.get("filename") if document is not None else document_id).strip()
    user_id = coerce_int(job.get("user_id")) or 0
    if user_id <= 0 and document is not None:
        user_id = coerce_int(document.get("user_id")) or 0
    await record_worker_knowledge_prompt_event(
        worker,
        logger=logger,
        conv_id=conv_id,
        user_id=user_id,
        event_type=event_type,
        document_names=(filename or document_id,),
        document_count=1,
        details={"document_id": document_id, "task_id": task_id, "message": detail_message},
        operation=operation,
    )


async def record_worker_knowledge_prompt_event(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    conv_id: str,
    user_id: int,
    event_type: KnowledgePromptEventType,
    document_names: tuple[str, ...],
    document_count: int,
    details: JSONDict,
    operation: str,
) -> None:
    if user_id <= 0:
        return
    await record_knowledge_prompt_event_and_publish(
        database_knowledge_prompt_state=worker.database_knowledge_prompt_state,
        event_bus=worker.event_bus,
        logger=logger,
        conv_id=conv_id,
        user_id=user_id,
        event_type=event_type,
        document_names=document_names,
        document_count=document_count,
        details=details,
        operation=operation,
    )
