"""SoAI - WebUI attachment cleanup pass [backend/app/background/webui_attachment_cleanup_run.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_event_payloads import (
    conversation_attachment_changed_event,
    knowledge_attachment_changed_event,
)
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.managed_file_deletion import delete_managed_file
from core.timing.epoch import epoch_ms
from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_trimmed_non_empty_str,
)
from database.repositories.users.conversation_attachment_knowledge_deletion import (
    sync_delete_knowledge_attachment_by_id,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.attachments.protocols_database import (
        DatabaseConversationAttachmentsProtocol,
        DatabaseConversationKnowledgeAttachmentsProtocol,
    )
    from core.database.protocols import DatabaseCoreProtocol
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONValue

    type AttachmentCleanupRow = Mapping[str, JSONValue | bytes]

__all__ = ("run_webui_attachment_cleanup",)

OPERATION_EXPIRED = "app.background.webui_attachment_cleanup.expired_staged_cleanup"
OPERATION_KNOWLEDGE_EXPIRED = "app.background.webui_attachment_cleanup.expired_knowledge_cleanup"
_ATTACHMENT_CLEANUP_ROW_LABEL = "Attachment cleanup field"


def _attachment_cleanup_str(
    row: AttachmentCleanupRow,
    field_name: str,
) -> str:
    return require_sqlite_row_trimmed_non_empty_str(
        row,
        field_name,
        label=_ATTACHMENT_CLEANUP_ROW_LABEL,
    )


def _attachment_cleanup_int(
    row: AttachmentCleanupRow,
    field_name: str,
) -> int:
    return require_sqlite_row_int(
        row,
        field_name,
        label=_ATTACHMENT_CLEANUP_ROW_LABEL,
        minimum=None,
    )


async def _cleanup_expired_physical_attachments(
    *,
    database_attachments: DatabaseConversationAttachmentsProtocol,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    storage_root: str,
    batch_limit: int,
) -> int:
    cleaned = 0
    cursor_expires_at_ms: int | None = None
    cursor_attachment_id: str | None = None
    now_ms = epoch_ms()
    while True:
        expired = await database_attachments.list_unbound_attachment_cleanup(
            now_ms=now_ms,
            limit=batch_limit,
            cursor_expires_at_ms=cursor_expires_at_ms,
            cursor_attachment_id=cursor_attachment_id,
        )
        if not expired:
            return cleaned
        for attachment in expired:
            cursor_expires_at_ms = _attachment_cleanup_int(attachment, "expires_at_ms")
            cursor_attachment_id = _attachment_cleanup_str(attachment, "attachment_id")
            try:
                deletion_mark = await database_attachments.mark_reclaimable_attachment_unused(
                    conv_id=_attachment_cleanup_str(attachment, "conv_id"),
                    user_id=_attachment_cleanup_int(attachment, "user_id"),
                    attachment_id=cursor_attachment_id,
                    updated_at_ms=now_ms,
                )
                if deletion_mark is None:
                    continue
                await event_bus.publish(conversation_attachment_changed_event(deletion_mark))
                deletion_plan = await database_attachments.prepare_unbound_attachment_deletion(
                    conv_id=_attachment_cleanup_str(attachment, "conv_id"),
                    user_id=_attachment_cleanup_int(attachment, "user_id"),
                    attachment_id=cursor_attachment_id,
                )
                if deletion_plan is None:
                    continue
                if not deletion_plan.requires_file_deletion:
                    cleaned += 1
                    continue
                await delete_managed_file(
                    storage_root, _attachment_cleanup_str(attachment, "file_path")
                )
                finalized = await database_attachments.finalize_unbound_attachment_deletion(
                    conv_id=_attachment_cleanup_str(attachment, "conv_id"),
                    user_id=_attachment_cleanup_int(attachment, "user_id"),
                    attachment_id=cursor_attachment_id,
                )
                if finalized is not None:
                    cleaned += 1
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to clean up expired WebUI attachment.",
                    operation=OPERATION_EXPIRED,
                    details={"attachment_id": cursor_attachment_id},
                    level="warning",
                )


async def _expire_draft_knowledge_attachments(
    *,
    database_core: DatabaseCoreProtocol,
    database_knowledge: DatabaseConversationKnowledgeAttachmentsProtocol,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    batch_limit: int,
) -> int:
    expired_count = 0
    cursor_expires_at_ms: int | None = None
    cursor_knowledge_attachment_id: str | None = None
    now_ms = epoch_ms()
    while True:
        expired = await database_knowledge.list_reclaimable_knowledge_attachments(
            now_ms=now_ms,
            limit=batch_limit,
            cursor_expires_at_ms=cursor_expires_at_ms,
            cursor_knowledge_attachment_id=cursor_knowledge_attachment_id,
        )
        if not expired:
            return expired_count
        for summary in expired:
            cursor_expires_at_ms = _attachment_cleanup_int(summary, "expires_at_ms")
            cursor_knowledge_attachment_id = _attachment_cleanup_str(
                summary,
                "knowledge_attachment_id",
            )
            try:
                if summary.get("state") == "unused":
                    deleted = await database_core.writer.queue_write_operation(
                        sync_delete_knowledge_attachment_by_id,
                        _attachment_cleanup_str(summary, "conv_id"),
                        _attachment_cleanup_int(summary, "user_id"),
                        cursor_knowledge_attachment_id,
                    )
                    if deleted is not None:
                        expired_count += 1
                    continue
                updated = await database_knowledge.finalize_knowledge_attachment_by_id(
                    conv_id=_attachment_cleanup_str(summary, "conv_id"),
                    user_id=_attachment_cleanup_int(summary, "user_id"),
                    knowledge_attachment_id=cursor_knowledge_attachment_id,
                    processing_state="cancelled",
                    terminal_item_status="cancelled",
                    error_message="Knowledge attachment expired before claim.",
                    state="unused",
                )
                if updated is not None:
                    await event_bus.publish(knowledge_attachment_changed_event(updated))
                    expired_count += 1
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to expire draft WebUI knowledge attachment.",
                    operation=OPERATION_KNOWLEDGE_EXPIRED,
                    details={"knowledge_attachment_id": cursor_knowledge_attachment_id},
                    level="warning",
                )


async def run_webui_attachment_cleanup(
    *,
    database_core: DatabaseCoreProtocol,
    database_attachments: DatabaseConversationAttachmentsProtocol,
    database_knowledge: DatabaseConversationKnowledgeAttachmentsProtocol,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    storage_root: str,
    batch_limit: int,
) -> tuple[int, int]:
    physical_count = await _cleanup_expired_physical_attachments(
        database_attachments=database_attachments,
        event_bus=event_bus,
        logger=logger,
        storage_root=storage_root,
        batch_limit=batch_limit,
    )
    knowledge_count = await _expire_draft_knowledge_attachments(
        database_core=database_core,
        database_knowledge=database_knowledge,
        event_bus=event_bus,
        logger=logger,
        batch_limit=batch_limit,
    )
    return physical_count, knowledge_count
