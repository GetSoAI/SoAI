"""SoAI - Direct attachment permanent storage [backend/core/attachments/direct_upload_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.attachments.attachment_constants import STAGED_ATTACHMENT_TTL_MS
from core.attachments.direct_upload_metadata import (
    normalize_direct_upload_mime_type,
    resolve_direct_upload_preview_type,
)
from core.files.move_with_cancellation import move_file_with_cancellation
from core.hardware.reservation_claims import claim_reserved_write
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.tasks.protocols import (
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TokenCollectionProtocol,
    )

__all__ = (
    "StoredDirectAttachmentUpload",
    "build_stored_direct_attachment_upload",
    "move_direct_attachment_to_storage",
)


@dataclass(frozen=True, slots=True)
class StoredDirectAttachmentUpload:
    file_id: str
    file_path: str
    filename: str
    mime_type: str
    size_bytes: int
    content_sha256: str
    preview_type: str
    created_at_ms: int
    expires_at_ms: int


async def move_direct_attachment_to_storage(
    *,
    temp_path: str,
    permanent_path: str,
    size_bytes: int,
    storage_manager: StorageManagerProtocol,
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    cancellation_id: str,
) -> None:
    async with cancellation_token_scope(
        token_collection,
        cancellation_history,
        cancellation_event_bus,
        cancellation_id=cancellation_id,
        owner="chat_direct_attachment_upload",
        metadata={"path": permanent_path},
    ) as token:
        with storage_manager.reserve_disk_space(
            path=permanent_path,
            required_bytes=size_bytes,
            operation="chat.direct_attachment_upload.move",
            details={"purpose": "chat_direct_attachment_storage", "path": permanent_path},
        ) as reservation:
            with claim_reserved_write(reservation, size_bytes=size_bytes):
                await move_file_with_cancellation(temp_path, permanent_path, token)
        token.raise_if_cancelled()


def build_stored_direct_attachment_upload(
    *,
    file_id: str,
    permanent_path: str,
    safe_filename: str,
    declared_content_type: str | None,
    size_bytes: int,
    content_sha256: str,
) -> StoredDirectAttachmentUpload:
    created_at_ms = epoch_ms()
    mime_type = normalize_direct_upload_mime_type(declared_content_type)
    return StoredDirectAttachmentUpload(
        file_id=file_id,
        file_path=permanent_path,
        filename=safe_filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        content_sha256=content_sha256,
        preview_type=resolve_direct_upload_preview_type(safe_filename, mime_type),
        created_at_ms=created_at_ms,
        expires_at_ms=created_at_ms + STAGED_ATTACHMENT_TTL_MS,
    )
