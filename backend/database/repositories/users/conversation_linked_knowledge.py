"""SoAI - Conversation linked knowledge repository service [backend/database/repositories/users/conversation_linked_knowledge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.users.conversation_linked_knowledge_catalog_queries import (
    list_reusable_knowledge_attachments_query,
)
from database.repositories.users.conversation_linked_knowledge_queries import (
    get_linked_knowledge_item_preview_query,
    prepare_linked_knowledge_use_query,
)
from database.repositories.users.conversation_linked_knowledge_writes import (
    sync_use_linked_knowledge_items,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseConversationLinkedKnowledge",)


class DatabaseConversationLinkedKnowledge:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def list_reusable_knowledge_attachments(
        self,
        *,
        user_id: int,
        query: str | None,
        limit: int,
    ) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            list_reusable_knowledge_attachments_query,
            user_id,
            query,
            limit,
        )

    async def preview_linked_knowledge_item(
        self,
        *,
        source_conv_id: str,
        source_user_id: int,
        source_knowledge_attachment_id: str,
        item_id: int,
        document_id: str | None,
    ) -> JSONDict:
        return await self.core.reader.execute_read(
            get_linked_knowledge_item_preview_query,
            source_conv_id,
            source_user_id,
            source_knowledge_attachment_id,
            item_id,
            document_id,
        )

    async def prepare_linked_knowledge_use(
        self,
        *,
        target_conv_id: str,
        target_user_id: int,
        source_conv_id: str,
        source_user_id: int,
        source_knowledge_attachment_id: str,
        item_ids: tuple[int, ...],
        client_batch_id: str,
    ) -> JSONDict:
        return await self.core.reader.execute_read(
            prepare_linked_knowledge_use_query,
            target_conv_id,
            target_user_id,
            source_conv_id,
            source_user_id,
            source_knowledge_attachment_id,
            item_ids,
            client_batch_id,
        )

    async def use_linked_knowledge_items(
        self,
        *,
        target_conv_id: str,
        target_user_id: int,
        source_conv_id: str,
        source_user_id: int,
        source_knowledge_attachment_id: str,
        item_ids: tuple[int, ...],
        client_batch_id: str,
        reservation: DiskSpaceReservationLeaseProtocol,
        reservation_bytes: int,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_use_linked_knowledge_items,
            target_conv_id,
            target_user_id,
            source_conv_id,
            source_user_id,
            source_knowledge_attachment_id,
            item_ids,
            client_batch_id,
            reservation,
            reservation_bytes,
        )
