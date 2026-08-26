"""SoAI - Reindex terminal knowledge prompt events [backend/mcp/worker/processors/reindex_terminal_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.worker.knowledge_prompt_recording import record_worker_knowledge_prompt_event

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.rag.knowledge_prompt_types import KnowledgePromptEventType
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "ReindexTerminalEventContext",
    "record_reindex_cancelled_event",
    "record_reindex_completed_event",
    "record_reindex_failed_event",
)

OPERATION_MCP_WORKER_REINDEX_KNOWLEDGE_PROMPT_EVENT = "mcp.worker.reindex.knowledge_prompt_event"


@dataclass(frozen=True, slots=True)
class ReindexTerminalEventContext:
    conv_id: str
    user_id: int
    task_id: str
    document_count: int


async def record_reindex_completed_event(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    context: ReindexTerminalEventContext,
) -> None:
    await _record_reindex_terminal_event(
        worker,
        logger=logger,
        context=context,
        event_type="knowledge_reindex_completed",
        detail_message="Reindex completed",
    )


async def record_reindex_cancelled_event(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    context: ReindexTerminalEventContext,
    reason: str,
) -> None:
    await _record_reindex_terminal_event(
        worker,
        logger=logger,
        context=context,
        event_type="knowledge_reindex_cancelled",
        detail_message=reason,
    )


async def record_reindex_failed_event(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    context: ReindexTerminalEventContext,
    error_message: str,
) -> None:
    await _record_reindex_terminal_event(
        worker,
        logger=logger,
        context=context,
        event_type="knowledge_reindex_failed",
        detail_message=error_message,
    )


async def _record_reindex_terminal_event(
    worker: MCPWorkerProtocol,
    *,
    logger: LoggerProtocol,
    context: ReindexTerminalEventContext,
    event_type: KnowledgePromptEventType,
    detail_message: str,
) -> None:
    details: JSONDict = {"task_id": context.task_id, "message": detail_message}
    await record_worker_knowledge_prompt_event(
        worker,
        logger=logger,
        conv_id=context.conv_id,
        user_id=context.user_id,
        event_type=event_type,
        document_names=(),
        document_count=max(0, int(context.document_count)),
        details=details,
        operation=OPERATION_MCP_WORKER_REINDEX_KNOWLEDGE_PROMPT_EVENT,
    )
