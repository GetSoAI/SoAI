"""SoAI - Canonical direct attachment parsing [backend/features/chat/direct_attachment_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.attachments.attachment_constants import WEBUI_CHAT_ATTACHMENT_PURPOSE
from core.attachments.attachment_event_payloads import conversation_attachment_changed_event
from core.attachments.attachment_parse_classification import (
    classify_attachment_descriptor_for_provider,
)
from core.attachments.attachment_parse_failure import mark_attachment_parse_failed
from core.attachments.attachment_parse_persistence import persist_attachment_parse_outcome
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.content_hashing import hash_descriptor_content
from core.files.managed_file_opening import ManagedFileDescriptor, open_managed_file_descriptor
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.storage_root_resolution import resolve_managed_files_storage_root
from core.logging.trace import get_logger
from core.media.config import resolve_media_parse_timeout
from core.timing.epoch import epoch_ms
from core.validation.strict_numbers import require_non_negative_int_strict
from features.api.runtime.webui_attachments.provider_text_settings import (
    read_provider_text_settings,
)

if TYPE_CHECKING:
    from typing import Literal

    from core.attachments.protocols_database import DatabaseConversationAttachmentsProtocol
    from core.config.protocols import ConfigProtocol
    from core.events.protocols import EventBusProtocol
    from core.files.protocols import (
        DatabaseFilesProtocol,
        DocumentReaderProtocol,
        FileParserRegistryFactoryProtocol,
        FilesPathResolverProtocol,
    )
    from core.types.json import JSONDict

    type DirectAttachmentParseStatus = Literal["parsed", "failed", "stale"]

__all__ = (
    "DirectAttachmentParseDependencies",
    "DirectAttachmentParseResult",
    "parse_direct_attachment",
)

LOGGER_NAME = "SoAI.features.chat.direct_attachment_parsing"
OPERATION = "chat.direct_attachment.parse"
DIRECT_ATTACHMENT_PARSE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *HANDLED_RUNTIME_EXCEPTIONS,
    FileStorageSecurityError,
)


@dataclass(frozen=True, slots=True)
class DirectAttachmentParseDependencies:
    config: ConfigProtocol
    files: FilesPathResolverProtocol
    database_files: DatabaseFilesProtocol
    database_attachments: DatabaseConversationAttachmentsProtocol
    document_reader: DocumentReaderProtocol
    parser_registry_factory: FileParserRegistryFactoryProtocol
    event_bus: EventBusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DirectAttachmentParseDependencies",
            config=self.config,
            files=self.files,
            database_files=self.database_files,
            database_attachments=self.database_attachments,
            document_reader=self.document_reader,
            parser_registry_factory=self.parser_registry_factory,
            event_bus=self.event_bus,
        )


@dataclass(frozen=True, slots=True)
class DirectAttachmentParseResult:
    status: DirectAttachmentParseStatus
    attachment: JSONDict | None


def _require_attachment_string(attachment: JSONDict, field_name: str) -> str:
    value = attachment.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise FileStorageSecurityError("Attachment metadata is invalid.")
    return value


def _close_managed_file_descriptor(managed: ManagedFileDescriptor) -> None:
    os.close(managed.descriptor)


async def _open_verified_attachment_descriptor(
    *,
    deps: DirectAttachmentParseDependencies,
    attachment: JSONDict,
    user_id: int,
) -> int:
    file_id = _require_attachment_string(attachment, "file_id")
    record = await deps.database_files.get_file_info_with_path(
        file_id,
        enforce_owner=True,
        user_id=user_id,
        api_key_id=None,
    )
    if record is None:
        raise FileStorageSecurityError("Attachment file catalog row is missing.")
    if record["purpose"] != WEBUI_CHAT_ATTACHMENT_PURPOSE or record["api_key_id"] is not None:
        raise FileStorageSecurityError("Attachment file catalog row is invalid.")
    managed = await run_joined_thread_call(
        open_managed_file_descriptor,
        resolve_managed_files_storage_root(deps.config, deps.files),
        record["file_path"],
        task_name="direct-attachment-managed-open",
        cancelled_result_cleanup=_close_managed_file_descriptor,
    )
    completed = False
    try:
        try:
            content_hash = await run_joined_thread_call(
                hash_descriptor_content,
                managed.descriptor,
                task_name="direct-attachment-content-hash",
            )
        except ValidationError as exception:
            raise FileStorageSecurityError(
                "Attachment file content could not be verified before parsing.",
            ) from exception
        if (
            content_hash.size_bytes != record["size_bytes"]
            or content_hash.sha256_hex != record["content_sha256"]
            or managed.size_bytes != record["size_bytes"]
        ):
            raise FileStorageSecurityError("Attachment file content changed before parsing.")
        completed = True
        return managed.descriptor
    finally:
        if not completed:
            os.close(managed.descriptor)


async def _publish_attachment(
    deps: DirectAttachmentParseDependencies,
    attachment: JSONDict | None,
) -> None:
    if attachment is not None:
        await deps.event_bus.publish(conversation_attachment_changed_event(attachment))


async def parse_direct_attachment(
    *,
    deps: DirectAttachmentParseDependencies,
    attachment: JSONDict,
) -> DirectAttachmentParseResult:
    conv_id = _require_attachment_string(attachment, "conv_id")
    attachment_id = _require_attachment_string(attachment, "attachment_id")
    user_id = require_non_negative_int_strict(
        attachment.get("user_id"),
        error_message="Attachment user_id is invalid.",
    )
    try:
        settings = read_provider_text_settings(deps.config)
        filename = _require_attachment_string(attachment, "filename")
        mime_type = _require_attachment_string(attachment, "mime_type")
        descriptor = await _open_verified_attachment_descriptor(
            deps=deps,
            attachment=attachment,
            user_id=user_id,
        )
        try:
            outcome = await classify_attachment_descriptor_for_provider(
                document_reader=deps.document_reader,
                parser_registry_factory=deps.parser_registry_factory,
                descriptor=descriptor,
                filename=filename,
                mime_type=mime_type,
                max_chars=settings.max_store_chars,
                parse_timeout_sec=resolve_media_parse_timeout(
                    deps.config,
                    filename=filename,
                    mime_type=mime_type,
                    default_timeout_seconds=settings.upload_parse_timeout_sec,
                ),
            )
        finally:
            os.close(descriptor)
        updated = await persist_attachment_parse_outcome(
            deps.database_attachments,
            conv_id=conv_id,
            user_id=user_id,
            attachment_id=attachment_id,
            outcome=outcome,
            now_ms=epoch_ms(),
        )
        await _publish_attachment(deps, updated)
        return DirectAttachmentParseResult(
            status="parsed" if updated is not None else "stale",
            attachment=updated,
        )
    except DIRECT_ATTACHMENT_PARSE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Direct attachment parsing failed.",
            operation=OPERATION,
            details={"attachment_id": attachment_id},
        )
        failed = await mark_attachment_parse_failed(
            deps.database_attachments,
            conv_id=conv_id,
            user_id=user_id,
            attachment_id=attachment_id,
            parse_error="Attachment parsing failed.",
        )
        await _publish_attachment(deps, failed)
        return DirectAttachmentParseResult(
            status="failed" if failed is not None else "stale",
            attachment=failed,
        )
