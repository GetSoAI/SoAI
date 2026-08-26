"""SoAI - Source-agnostic direct attachment ingestion [backend/features/chat/direct_attachment_ingestion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.attachments.direct_upload_metadata import (
    ensure_existing_direct_upload_matches,
    normalize_direct_upload_declared_size,
    normalize_direct_upload_mime_type,
    require_direct_upload_client_id,
    resolve_direct_upload_display_name,
)
from core.attachments.direct_upload_persistence import StoredDirectAttachmentUpload
from core.attachments.direct_upload_storage import (
    store_direct_attachment_upload,
    store_staged_direct_attachment_upload,
)
from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.di.validation import require_dependencies
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.storage_root_resolution import resolve_managed_files_storage_root
from core.files.upload_cleanup import cleanup_upload_artifacts

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.attachments.protocols_database import DatabaseConversationAttachmentsProtocol
    from core.config.protocols import ConfigProtocol
    from core.files.protocols import FilesPathResolverProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.tasks.protocols import (
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TokenCollectionProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "DirectAttachmentIngestionDependencies",
    "DirectAttachmentIngestionResult",
    "ingest_direct_attachment",
    "ingest_staged_direct_attachment",
)


@dataclass(frozen=True, slots=True)
class DirectAttachmentIngestionDependencies:
    config: ConfigProtocol
    files: FilesPathResolverProtocol
    database_attachments: DatabaseConversationAttachmentsProtocol
    storage_manager: StorageManagerProtocol
    token_collection: TokenCollectionProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DirectAttachmentIngestionDependencies",
            config=self.config,
            files=self.files,
            database_attachments=self.database_attachments,
            storage_manager=self.storage_manager,
            token_collection=self.token_collection,
            cancellation_history=self.cancellation_history,
            cancellation_event_bus=self.cancellation_event_bus,
        )


@dataclass(frozen=True, slots=True)
class DirectAttachmentIngestionResult:
    attachment: JSONDict
    created: bool


async def _persist_direct_attachment(
    *,
    deps: DirectAttachmentIngestionDependencies,
    stored: StoredDirectAttachmentUpload,
    conv_id: str,
    user_id: int,
    normalized_client_id: str,
) -> DirectAttachmentIngestionResult:
    try:
        staged = await deps.database_attachments.stage_physical_attachment(
            conv_id=conv_id,
            user_id=user_id,
            file_id=stored.file_id,
            file_path=stored.file_path,
            filename=stored.filename,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            content_sha256=stored.content_sha256,
            preview_type=stored.preview_type,
            client_attachment_id=normalized_client_id,
            created_at_ms=stored.created_at_ms,
            expires_at_ms=stored.expires_at_ms,
        )
    except HANDLED_RUNTIME_EXCEPTIONS:
        await cleanup_upload_artifacts(temp_path=None, permanent_path=stored.file_path)
        raise
    created = staged.get("file_id") == stored.file_id
    if not created:
        await cleanup_upload_artifacts(temp_path=None, permanent_path=stored.file_path)
    return DirectAttachmentIngestionResult(attachment=staged, created=created)


async def ingest_direct_attachment(
    *,
    deps: DirectAttachmentIngestionDependencies,
    read_chunk: Callable[[int], Awaitable[bytes]],
    declared_size: int | None,
    declared_content_type: str | None,
    display_name: str,
    source_filename: str | None,
    conv_id: str,
    user_id: int,
    client_attachment_id: str,
    cancellation_id: str,
) -> DirectAttachmentIngestionResult:
    normalized_client_id = require_direct_upload_client_id(client_attachment_id)
    filename = resolve_direct_upload_display_name(display_name, source_filename)
    mime_type = normalize_direct_upload_mime_type(declared_content_type)
    normalized_size = normalize_direct_upload_declared_size(declared_size)
    existing = await deps.database_attachments.get_attachment_by_client_id(
        conv_id=conv_id,
        user_id=user_id,
        client_attachment_id=normalized_client_id,
    )
    if existing is not None:
        ensure_existing_direct_upload_matches(
            existing,
            filename=filename,
            mime_type=mime_type,
            size_bytes=normalized_size,
        )
        return DirectAttachmentIngestionResult(attachment=existing, created=False)
    stored = await store_direct_attachment_upload(
        read_chunk=read_chunk,
        declared_size=normalized_size,
        declared_content_type=declared_content_type,
        display_name=filename,
        storage_root=resolve_managed_files_storage_root(deps.config, deps.files),
        max_bytes=resolve_upload_limit_bytes(deps.config, UploadLimitType.FILE),
        storage_manager=deps.storage_manager,
        token_collection=deps.token_collection,
        cancellation_history=deps.cancellation_history,
        cancellation_event_bus=deps.cancellation_event_bus,
        cancellation_id=cancellation_id,
    )
    return await _persist_direct_attachment(
        deps=deps,
        stored=stored,
        conv_id=conv_id,
        user_id=user_id,
        normalized_client_id=normalized_client_id,
    )


async def ingest_staged_direct_attachment(
    *,
    deps: DirectAttachmentIngestionDependencies,
    staged_path: str,
    staged_size: int,
    staged_sha256: str,
    declared_content_type: str | None,
    display_name: str,
    source_filename: str | None,
    conv_id: str,
    user_id: int,
    client_attachment_id: str,
    cancellation_id: str,
) -> DirectAttachmentIngestionResult:
    normalized_client_id = require_direct_upload_client_id(client_attachment_id)
    filename = resolve_direct_upload_display_name(display_name, source_filename)
    stored = await store_staged_direct_attachment_upload(
        staged_path=staged_path,
        staged_size=staged_size,
        staged_sha256=staged_sha256,
        declared_content_type=declared_content_type,
        display_name=filename,
        storage_root=resolve_managed_files_storage_root(deps.config, deps.files),
        max_bytes=resolve_upload_limit_bytes(deps.config, UploadLimitType.FILE),
        storage_manager=deps.storage_manager,
        token_collection=deps.token_collection,
        cancellation_history=deps.cancellation_history,
        cancellation_event_bus=deps.cancellation_event_bus,
        cancellation_id=cancellation_id,
    )
    return await _persist_direct_attachment(
        deps=deps,
        stored=stored,
        conv_id=conv_id,
        user_id=user_id,
        normalized_client_id=normalized_client_id,
    )
