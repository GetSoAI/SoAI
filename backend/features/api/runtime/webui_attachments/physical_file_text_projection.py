"""SoAI - Provider text projection for WebUI physical file attachments [backend/features/api/runtime/webui_attachments/physical_file_text_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.attachments.attachment_parse_classification import (
    classify_attachment_descriptor_for_provider,
)
from core.files.managed_storage_errors import FileStorageSecurityError
from core.text.chunked_reads import slice_chunked_text
from core.users.ocr_preferences import resolve_user_ocr_language
from features.api.runtime.webui_attachments.physical_file_snapshot import (
    open_verified_soai_file_descriptor,
)
from features.api.runtime.webui_attachments.provider_descriptor_snapshot import (
    close_provider_descriptor_snapshot,
)
from features.api.runtime.webui_attachments.provider_text_rendering import (
    build_file_content_unavailable_text,
    build_inline_file_content_text,
    build_missing_text_extraction_text,
)
from features.api.runtime.webui_attachments.verified_provider_snapshot import (
    load_verified_provider_descriptor_snapshot,
)

if TYPE_CHECKING:
    from core.files.database_types import FileCatalogRecordWithPath
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.projection_context import (
        WebuiAttachmentProjectionContext,
    )

__all__ = (
    "file_content_header",
    "file_identity_available",
    "pending_file_text_part",
    "ready_file_text_part",
)


def file_content_header(attachment: JSONDict) -> str:
    filename = str(attachment.get("filename") or "attachment")
    mime_type = str(attachment.get("mime_type") or "application/octet-stream")
    size_bytes = attachment.get("size_bytes")
    size_text = str(size_bytes) if isinstance(size_bytes, int) else "unknown"
    return f"Attached file: {filename}; MIME type={mime_type}; size={size_text} bytes."


def ready_file_text_part(
    context: WebuiAttachmentProjectionContext,
    *,
    attachment: JSONDict,
    provider_text: str,
) -> JSONDict:
    sliced = slice_chunked_text(
        content=provider_text,
        max_chars=context.provider_text_char_budget,
        offset_chars=0,
        content_complete=not bool(attachment.get("provider_text_truncated")),
    )
    return {
        "type": "text",
        "text": build_inline_file_content_text(
            header=file_content_header(attachment),
            content=sliced.content,
            truncated=sliced.truncated,
        ),
    }


async def pending_file_text_part(
    context: WebuiAttachmentProjectionContext,
    *,
    record: FileCatalogRecordWithPath,
    attachment: JSONDict,
) -> JSONDict:
    snapshot = await load_verified_provider_descriptor_snapshot(
        context.storage_root,
        record=record,
        attachment=attachment,
    )
    if snapshot is None:
        return {
            "type": "text",
            "text": build_file_content_unavailable_text(
                header=file_content_header(attachment),
                reason="Attachment file content changed.",
            ),
        }
    try:
        outcome = await classify_attachment_descriptor_for_provider(
            ocr_language=await resolve_user_ocr_language(
                context.dependencies.database_users, context.user_id
            ),
            document_reader=context.dependencies.document_reader,
            parser_registry_factory=context.dependencies.parser_registry_factory,
            descriptor=snapshot.descriptor,
            filename=str(attachment.get("filename") or ""),
            mime_type=str(attachment.get("mime_type") or ""),
            max_chars=context.provider_text_char_budget,
        )
    finally:
        close_provider_descriptor_snapshot(snapshot)
    if isinstance(outcome.provider_text, str) and outcome.provider_text.strip():
        return {
            "type": "text",
            "text": build_inline_file_content_text(
                header=file_content_header(attachment),
                content=outcome.provider_text.strip(),
                truncated=bool(outcome.provider_text_truncated),
            ),
        }
    if outcome.parse_state == "failed":
        return {
            "type": "text",
            "text": build_file_content_unavailable_text(
                header=file_content_header(attachment),
                reason=outcome.parse_error,
            ),
        }
    return {
        "type": "text",
        "text": build_missing_text_extraction_text(header=file_content_header(attachment)),
    }


async def file_identity_available(
    context: WebuiAttachmentProjectionContext,
    *,
    record: FileCatalogRecordWithPath,
    attachment: JSONDict,
) -> bool:
    try:
        managed = await open_verified_soai_file_descriptor(
            context.storage_root,
            record=record,
            attachment=attachment,
        )
    except FileStorageSecurityError:
        return False
    os.close(managed.descriptor)
    return True
