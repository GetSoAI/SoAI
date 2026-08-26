"""SoAI - Conversation attachment repository service [backend/database/repositories/users/conversation_attachments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.users.conversation_attachment_deletion_sync import (
    sync_finalize_unbound_attachment_deletion,
    sync_mark_reclaimable_attachment_unused,
    sync_mark_unbound_attachment_unused,
    sync_prepare_unbound_attachment_deletion,
)
from database.repositories.users.conversation_attachment_physical_sync import (
    sync_stage_conversation_attachment,
    sync_update_attachment_parse_state,
)
from database.repositories.users.conversation_attachment_queries import (
    get_attachment_by_client_id_query,
    get_attachment_query,
)
from database.repositories.users.conversation_attachment_recovery_queries import (
    list_pending_parse_attachments_query,
    list_unbound_attachment_cleanup_query,
)

if TYPE_CHECKING:
    from core.attachments.attachment_deletion import AttachmentDeletionPlan
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseConversationAttachments",)


class DatabaseConversationAttachments:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def stage_physical_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        file_id: str,
        file_path: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        content_sha256: str,
        preview_type: str,
        client_attachment_id: str,
        created_at_ms: int,
        expires_at_ms: int,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_stage_conversation_attachment,
            conv_id,
            user_id,
            file_id,
            file_path,
            filename,
            mime_type,
            size_bytes,
            content_sha256,
            preview_type,
            client_attachment_id,
            created_at_ms,
            expires_at_ms,
        )

    async def get_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            get_attachment_query,
            conv_id,
            user_id,
            attachment_id,
        )

    async def get_attachment_by_client_id(
        self,
        *,
        conv_id: str,
        user_id: int,
        client_attachment_id: str,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            get_attachment_by_client_id_query,
            conv_id,
            user_id,
            client_attachment_id,
        )

    async def update_attachment_parse_state(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
        provider_mode: str | None,
        provider_text: str | None,
        provider_text_truncated: bool | None,
        parse_state: str,
        parse_error: str | None,
        parsed_at_ms: int | None,
        updated_at_ms: int,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_update_attachment_parse_state,
            conv_id,
            user_id,
            attachment_id,
            provider_mode,
            provider_text,
            provider_text_truncated,
            parse_state,
            parse_error,
            parsed_at_ms,
            updated_at_ms,
        )

    async def mark_unbound_attachment_unused(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
        updated_at_ms: int,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_mark_unbound_attachment_unused,
            conv_id,
            user_id,
            attachment_id,
            updated_at_ms,
        )

    async def mark_reclaimable_attachment_unused(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
        updated_at_ms: int,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_mark_reclaimable_attachment_unused,
            conv_id,
            user_id,
            attachment_id,
            updated_at_ms,
        )

    async def prepare_unbound_attachment_deletion(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
    ) -> AttachmentDeletionPlan | None:
        return await self.core.writer.queue_write_operation(
            sync_prepare_unbound_attachment_deletion,
            conv_id,
            user_id,
            attachment_id,
        )

    async def finalize_unbound_attachment_deletion(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_finalize_unbound_attachment_deletion,
            conv_id,
            user_id,
            attachment_id,
        )

    async def list_unbound_attachment_cleanup(
        self,
        *,
        now_ms: int,
        limit: int,
        cursor_expires_at_ms: int | None,
        cursor_attachment_id: str | None,
    ) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            list_unbound_attachment_cleanup_query,
            now_ms,
            limit=limit,
            cursor_expires_at_ms=cursor_expires_at_ms,
            cursor_attachment_id=cursor_attachment_id,
        )

    async def list_pending_parse_attachments(
        self,
        *,
        limit: int,
        cursor_created_at_ms: int | None,
        cursor_attachment_id: str | None,
    ) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            list_pending_parse_attachments_query,
            limit=limit,
            cursor_created_at_ms=cursor_created_at_ms,
            cursor_attachment_id=cursor_attachment_id,
        )
