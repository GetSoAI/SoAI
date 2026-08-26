"""SoAI - WebUI attachment database protocol definitions [backend/core/attachments/protocols_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.attachments.attachment_deletion import AttachmentDeletionPlan
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict

__all__ = (
    "DatabaseConversationAttachmentsProtocol",
    "DatabaseConversationKnowledgeAttachmentsProtocol",
    "DatabaseConversationLinkedKnowledgeProtocol",
)


class DatabaseConversationAttachmentsProtocol(Protocol):
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
    ) -> JSONDict: ...
    async def get_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
    ) -> JSONDict | None: ...
    async def get_attachment_by_client_id(
        self,
        *,
        conv_id: str,
        user_id: int,
        client_attachment_id: str,
    ) -> JSONDict | None: ...
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
    ) -> JSONDict | None: ...
    async def mark_unbound_attachment_unused(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
        updated_at_ms: int,
    ) -> JSONDict | None: ...
    async def mark_reclaimable_attachment_unused(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
        updated_at_ms: int,
    ) -> JSONDict | None: ...
    async def prepare_unbound_attachment_deletion(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
    ) -> AttachmentDeletionPlan | None: ...
    async def finalize_unbound_attachment_deletion(
        self,
        *,
        conv_id: str,
        user_id: int,
        attachment_id: str,
    ) -> JSONDict | None: ...
    async def list_unbound_attachment_cleanup(
        self,
        *,
        now_ms: int,
        limit: int,
        cursor_expires_at_ms: int | None,
        cursor_attachment_id: str | None,
    ) -> list[JSONDict]: ...
    async def list_pending_parse_attachments(
        self,
        *,
        limit: int,
        cursor_created_at_ms: int | None,
        cursor_attachment_id: str | None,
    ) -> list[JSONDict]: ...


class DatabaseConversationKnowledgeAttachmentsProtocol(Protocol):
    async def list_draft_knowledge_attachments(
        self,
        *,
        conv_id: str,
        user_id: int,
        preview_limit: int,
    ) -> list[JSONDict]: ...
    async def list_reclaimable_knowledge_attachments(
        self,
        *,
        now_ms: int,
        limit: int,
        cursor_expires_at_ms: int | None,
        cursor_knowledge_attachment_id: str | None,
    ) -> list[JSONDict]: ...
    async def claim_knowledge_attachments(
        self,
        *,
        conv_id: str,
        user_id: int,
        selections: list[tuple[str, int]],
    ) -> list[JSONDict]: ...
    async def get_knowledge_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
    ) -> JSONDict | None: ...
    async def remove_draft_knowledge_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
    ) -> JSONDict: ...
    async def cancel_knowledge_attachment(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
    ) -> JSONDict: ...
    async def list_active_knowledge_attachment_task_ids(
        self,
        *,
        conv_id: str,
        user_id: int,
        knowledge_attachment_id: str,
    ) -> list[str]: ...
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
    ) -> JSONDict | None: ...
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
    ) -> JSONDict: ...
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
    ) -> JSONDict: ...
    async def finalize_knowledge_attachment_task(
        self,
        *,
        task_id: str,
        processing_state: str,
        terminal_item_status: str,
        error_message: str | None,
    ) -> JSONDict | None: ...
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
    ) -> JSONDict | None: ...


class DatabaseConversationLinkedKnowledgeProtocol(Protocol):
    async def list_reusable_knowledge_attachments(
        self,
        *,
        user_id: int,
        query: str | None,
        limit: int,
    ) -> list[JSONDict]: ...
    async def preview_linked_knowledge_item(
        self,
        *,
        source_conv_id: str,
        source_user_id: int,
        source_knowledge_attachment_id: str,
        item_id: int,
        document_id: str | None,
    ) -> JSONDict: ...
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
    ) -> JSONDict: ...
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
    ) -> JSONDict: ...
