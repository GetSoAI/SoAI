"""SoAI - WebUI RAG knowledge attachment failure recording [backend/features/api/routes/webui/conversation_rag/knowledge_attachment_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from features.api.routes.webui.conversation_attachments.events import (
    publish_knowledge_attachment_changed,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "finalize_knowledge_attachment_failure",
    "finalize_knowledge_attachment_task_failure",
    "record_terminal_knowledge_attachment_item",
)


async def finalize_knowledge_attachment_task_failure(
    *,
    api_context: ApiContext,
    task_id: str,
    processing_state: str,
    terminal_item_status: str,
    error_message: str,
) -> JSONDict | None:
    summary = await api_context.dependencies.database_conversation_knowledge_attachments.finalize_knowledge_attachment_task(
        task_id=task_id,
        processing_state=processing_state,
        terminal_item_status=terminal_item_status,
        error_message=error_message,
    )
    if summary is not None:
        await publish_knowledge_attachment_changed(
            api_context.dependencies.event_bus,
            summary=summary,
        )
    return summary


async def finalize_knowledge_attachment_failure(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    processing_state: str,
    terminal_item_status: str,
    error_message: str,
    state: str | None,
) -> JSONDict | None:
    summary = await api_context.dependencies.database_conversation_knowledge_attachments.finalize_knowledge_attachment_by_id(
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        processing_state=processing_state,
        terminal_item_status=terminal_item_status,
        error_message=error_message,
        state=state,
    )
    if summary is not None:
        await publish_knowledge_attachment_changed(
            api_context.dependencies.event_bus,
            summary=summary,
        )
    return summary


async def record_terminal_knowledge_attachment_item(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    item_index: int,
    filename: str,
    file_type: str | None,
    file_size_bytes: int | None,
    rag_status: str,
    operation_type: str,
    error_message: str,
) -> JSONDict:
    summary = await api_context.dependencies.database_conversation_knowledge_attachments.add_knowledge_attachment_item(
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        document_id=None,
        event_id=None,
        item_index=item_index,
        filename=filename,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        rag_status=rag_status,
        operation_type=operation_type,
        error_message=error_message,
        created_at_ms=epoch_ms(),
    )
    await publish_knowledge_attachment_changed(
        api_context.dependencies.event_bus,
        summary=summary,
    )
    return summary
