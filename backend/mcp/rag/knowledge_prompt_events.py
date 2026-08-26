"""SoAI - RAG Knowledge prompt event recording [backend/mcp/rag/knowledge_prompt_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_mcp import KnowledgePromptStateChangedEvent
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.rag.protocols import DatabaseKnowledgePromptStateProtocol
    from core.types.json import JSONDict

__all__ = ("record_knowledge_prompt_event_and_publish",)

KNOWLEDGE_PROMPT_EVENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


async def record_knowledge_prompt_event_and_publish(
    *,
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    conv_id: str,
    user_id: int,
    event_type: Literal[
        "documents_added",
        "documents_removed",
        "document_processing_completed",
        "document_processing_failed",
        "document_processing_cancelled",
        "knowledge_reindex_queued",
        "knowledge_reindex_completed",
        "knowledge_reindex_failed",
        "knowledge_reindex_cancelled",
    ],
    document_names: tuple[str, ...],
    document_count: int,
    details: JSONDict,
    operation: str,
) -> None:
    created_at_ms = int(epoch_ms())
    try:
        event = await database_knowledge_prompt_state.record_knowledge_event(
            conv_id=conv_id,
            user_id=user_id,
            event_type=event_type,
            document_names=document_names,
            document_count=document_count,
            details=details,
            created_at_ms=created_at_ms,
        )
        await event_bus.publish(
            KnowledgePromptStateChangedEvent(
                user_id=user_id,
                conv_id=conv_id,
                knowledge_event_id=event.id,
                reason=event_type,
                created_at_ms=created_at_ms,
            ),
        )
    except KNOWLEDGE_PROMPT_EVENT_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to record Knowledge prompt event.",
            operation=operation,
            details={
                "conv_id": conv_id,
                "user_id": user_id,
                "event_type": event_type,
            },
            level="warning",
        )
