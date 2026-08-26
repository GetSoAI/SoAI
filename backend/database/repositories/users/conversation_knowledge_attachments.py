"""SoAI - Conversation knowledge attachment repository service [backend/database/repositories/users/conversation_knowledge_attachments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.users.conversation_attachment_knowledge_activity import (
    list_active_knowledge_attachment_task_ids_query,
)
from database.repositories.users.conversation_attachment_knowledge_creation import (
    sync_ensure_knowledge_attachment,
)
from database.repositories.users.conversation_attachment_knowledge_draft_removal import (
    sync_remove_draft_knowledge_attachment,
)
from database.repositories.users.conversation_attachment_knowledge_finalization import (
    sync_finalize_knowledge_attachment_by_id,
    sync_finalize_knowledge_attachment_task,
)
from database.repositories.users.conversation_attachment_knowledge_items import (
    sync_add_knowledge_attachment_item,
)
from database.repositories.users.conversation_attachment_knowledge_sync import (
    sync_cancel_knowledge_attachment,
    sync_claim_knowledge_attachments,
)
from database.repositories.users.conversation_attachment_queries import (
    get_knowledge_attachment_items_page_query,
    get_knowledge_attachment_query,
    list_draft_knowledge_attachments_query,
)
from database.repositories.users.conversation_attachment_recovery_queries import (
    list_reclaimable_knowledge_attachments_query,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseConversationKnowledgeAttachments",)


class DatabaseConversationKnowledgeAttachments:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def list_draft_knowledge_attachments(
        self,
        *,
        conv_id: str,
        user_id: int,
        preview_limit: int,
    ) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            list_draft_knowledge_attachments_query,
            conv_id,
            user_id,
            preview_limit=preview_limit,
        )

    async def list_reclaimable_knowledge_attachments(
        self,
        *,
        now_ms: int,
        limit: int,
        cursor_expires_at_ms: int | None,
        cursor_knowledge_attachment_id: str | None,
    ) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            list_reclaimable_knowledge_attachments_query,
            now_ms,
            limit=limit,
            cursor_expires_at_ms=cursor_expires_at_ms,
            cursor_knowledge_attachment_id=cursor_knowledge_attachment_id,
        )

    async def claim_knowledge_attachments(
        self,
        *,
        conv_id: str,
        user_id: int,
        selections: list[tuple[str, int]],
    ) -> list[JSONDict]:
        return await self.core.writer.queue_write_operation(
            sync_claim_knowledge_attachments,
            conv_id,
            user_id,
            selections,
        )

    async def get_knowledge_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            get_knowledge_attachment_query,
            conv_id,
            user_id,
            knowledge_attachment_id,
        )

    async def remove_draft_knowledge_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_remove_draft_knowledge_attachment,
            conv_id,
            user_id,
            knowledge_attachment_id,
        )

    async def cancel_knowledge_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_cancel_knowledge_attachment,
            conv_id,
            user_id,
            knowledge_attachment_id,
        )

    async def list_active_knowledge_attachment_task_ids(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
    ) -> list[str]:
        return await self.core.reader.execute_read(
            list_active_knowledge_attachment_task_ids_query,
            conv_id,
            user_id,
            knowledge_attachment_id,
        )

    async def get_knowledge_attachment_items_page(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
        limit: int,
        cursor_item_index: int | None,
        cursor_id: int | None,
        status: str | None,
        query: str | None,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            get_knowledge_attachment_items_page_query,
            conv_id,
            user_id,
            knowledge_attachment_id,
            limit=limit,
            cursor_item_index=cursor_item_index,
            cursor_id=cursor_id,
            status=status,
            query=query,
        )

    async def ensure_knowledge_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        source_type: str,
        operation_type: str,
        title: str,
        root_label: str | None,
        root_virtual_path: str | None,
        task_id: str | None,
        client_batch_id: str | None,
        created_at_ms: int,
        expires_at_ms: int,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_ensure_knowledge_attachment,
            conv_id,
            user_id,
            source_type,
            operation_type,
            title,
            root_label,
            root_virtual_path,
            task_id,
            client_batch_id,
            created_at_ms,
            expires_at_ms,
        )

    async def add_knowledge_attachment_item(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
        document_id: str | None,
        event_id: int | None,
        item_index: int,
        filename: str,
        file_type: str | None,
        file_size_bytes: int | None,
        rag_status: str,
        operation_type: str,
        error_message: str | None,
        created_at_ms: int,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_add_knowledge_attachment_item,
            conv_id,
            user_id,
            knowledge_attachment_id,
            document_id,
            event_id,
            item_index,
            filename,
            file_type,
            file_size_bytes,
            rag_status,
            operation_type,
            error_message,
            created_at_ms,
        )

    async def finalize_knowledge_attachment_task(
        self,
        *,
        task_id: str,
        processing_state: str,
        terminal_item_status: str,
        error_message: str | None,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_finalize_knowledge_attachment_task,
            task_id,
            processing_state,
            terminal_item_status,
            error_message,
        )

    async def finalize_knowledge_attachment_by_id(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
        processing_state: str,
        terminal_item_status: str,
        error_message: str | None,
        state: str | None,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_finalize_knowledge_attachment_by_id,
            conv_id,
            user_id,
            knowledge_attachment_id,
            processing_state,
            terminal_item_status,
            error_message,
            state,
        )
