"""SoAI - WebUI physical attachment snapshot verification [backend/features/api/runtime/webui_attachments/physical_file_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.attachments.attachment_constants import WEBUI_CHAT_ATTACHMENT_PURPOSE
from core.errors.exceptions import ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.files.managed_file_opening import open_managed_file_descriptor
from core.files.managed_storage_errors import FileStorageSecurityError
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.files.database_types import FileCatalogRecordWithPath
    from core.types.json import JSONDict
    from features.api.runtime.webui_attachments.projection_context import (
        WebuiAttachmentProjectionContext,
    )

__all__ = (
    "load_soai_file_attachment",
    "load_soai_file_record",
    "open_verified_soai_file_descriptor",
)


def _metadata_field_matches(part: JSONDict, attachment: JSONDict, field_name: str) -> bool:
    return part.get(field_name) == attachment.get(field_name)


async def load_soai_file_attachment(
    context: WebuiAttachmentProjectionContext,
    *,
    part: JSONDict,
) -> JSONDict | None:
    attachment_id = str(part.get("attachment_id") or "")
    if not attachment_id:
        raise ValidationError("SoAI file attachment_id is required.")
    attachment = await context.dependencies.database_conversation_attachments.get_attachment(
        conv_id=context.conv_id,
        user_id=context.user_id,
        attachment_id=attachment_id,
    )
    if attachment is None:
        return None
    for field_name in (
        "file_id",
        "filename",
        "mime_type",
        "size_bytes",
        "preview_type",
        "created_at_ms",
    ):
        if not _metadata_field_matches(part, attachment, field_name):
            return None
    part_revision = part.get("attachment_revision")
    attachment_revision = attachment.get("attachment_revision")
    if not is_strict_int(part_revision):
        raise ValidationError("SoAI file attachment metadata changed before provider projection.")
    if not is_strict_int(attachment_revision):
        return None
    if part_revision == attachment_revision:
        return attachment
    return None


async def load_soai_file_record(
    context: WebuiAttachmentProjectionContext,
    *,
    attachment: JSONDict,
) -> FileCatalogRecordWithPath | None:
    file_id = str(attachment.get("file_id") or "")
    if not file_id:
        raise ValidationError("SoAI file catalog id is missing.")
    record = await context.dependencies.database_files.get_file_info_with_path(
        file_id,
        enforce_owner=True,
        user_id=context.user_id,
        api_key_id=None,
    )
    if record is None:
        return None
    if record["purpose"] != WEBUI_CHAT_ATTACHMENT_PURPOSE:
        raise ValidationError("SoAI file purpose is invalid.")
    if record["api_key_id"] is not None:
        raise ValidationError("SoAI file ownership is invalid.")
    return record


async def open_verified_soai_file_descriptor(
    context: WebuiAttachmentProjectionContext,
    *,
    record: FileCatalogRecordWithPath,
    attachment: JSONDict,
) -> int:
    managed = await asyncio.to_thread(
        open_managed_file_descriptor,
        context.storage_root,
        record["file_path"],
    )
    completed = False
    try:
        if managed.size_bytes != record["size_bytes"] or managed.size_bytes != attachment.get(
            "size_bytes",
        ):
            raise FileStorageSecurityError("SoAI file size changed.")
        try:
            content_hash = await asyncio.to_thread(hash_descriptor_content, managed.descriptor)
        except ValidationError as exception:
            raise FileStorageSecurityError(
                "SoAI file content could not be verified.",
            ) from exception
        if (
            content_hash.size_bytes != record["size_bytes"]
            or content_hash.sha256_hex != record["content_sha256"]
        ):
            raise FileStorageSecurityError("SoAI file content changed.")
        completed = True
        return managed.descriptor
    finally:
        if not completed:
            os.close(managed.descriptor)
