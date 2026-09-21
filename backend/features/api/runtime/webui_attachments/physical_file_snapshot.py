"""SoAI - WebUI physical attachment snapshot verification [backend/features/api/runtime/webui_attachments/physical_file_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.attachments.attachment_constants import WEBUI_CHAT_ATTACHMENT_PURPOSE
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.files.managed_file_opening import open_managed_file_descriptor
from core.files.managed_storage_errors import FileStorageSecurityError
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.attachments.protocols_database import DatabaseConversationAttachmentsProtocol
    from core.files.database_types import FileCatalogRecordWithPath
    from core.files.managed_file_opening import ManagedFileDescriptor
    from core.files.protocols import DatabaseFilesProtocol
    from core.types.json import JSONDict

__all__ = (
    "load_soai_file_attachment",
    "load_soai_file_record",
    "open_verified_soai_file_descriptor",
)


def _metadata_field_matches(part: JSONDict, attachment: JSONDict, field_name: str) -> bool:
    part_value = part.get(field_name)
    attachment_value = attachment.get(field_name)
    return type(part_value) is type(attachment_value) and part_value == attachment_value


def _require_catalog_record_authority(
    record: FileCatalogRecordWithPath,
    *,
    file_id: str,
    user_id: int,
) -> None:
    if record.get("id") != file_id:
        raise ValidationError("SoAI file catalog record identity is invalid.")
    if not is_strict_int(record.get("user_id")) or record.get("user_id") != user_id:
        raise ValidationError("SoAI file catalog record owner is invalid.")
    if record.get("purpose") != WEBUI_CHAT_ATTACHMENT_PURPOSE:
        raise ValidationError("Attachment file purpose is invalid.")
    if "api_key_id" not in record or record.get("api_key_id") is not None:
        raise ValidationError("Attachment file ownership is invalid.")
    if (
        not is_strict_int(record.get("size_bytes"))
        or record["size_bytes"] < 0
        or not isinstance(record.get("content_sha256"), str)
        or not is_canonical_sha256_hexdigest(record["content_sha256"])
        or not isinstance(record.get("file_path"), str)
        or not record["file_path"]
    ):
        raise ValidationError("SoAI file catalog record authority is invalid.")


async def load_soai_file_attachment(
    database_attachments: DatabaseConversationAttachmentsProtocol,
    *,
    conv_id: str,
    user_id: int,
    part: JSONDict,
) -> JSONDict | None:
    attachment_id = part.get("attachment_id")
    if not isinstance(attachment_id, str) or not attachment_id:
        raise ValidationError("SoAI file attachment_id is required.")
    attachment = await database_attachments.get_attachment(
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
    )
    if attachment is None:
        return None
    if (
        attachment.get("attachment_id") != attachment_id
        or attachment.get("conv_id") != conv_id
        or not is_strict_int(attachment.get("user_id"))
        or attachment.get("user_id") != user_id
        or attachment.get("file_id") != part.get("file_id")
    ):
        raise ValidationError("SoAI file attachment repository returned invalid identity.")
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
    database_files: DatabaseFilesProtocol,
    *,
    user_id: int,
    attachment: JSONDict,
) -> FileCatalogRecordWithPath | None:
    attachment_user_id = attachment.get("user_id")
    if not is_strict_int(attachment_user_id) or attachment_user_id != user_id:
        raise ValidationError("SoAI file owner is invalid.")
    file_id = attachment.get("file_id")
    if not isinstance(file_id, str) or not file_id:
        raise ValidationError("SoAI file catalog id is missing.")
    record = await database_files.get_file_info_with_path(
        file_id,
        enforce_owner=True,
        user_id=user_id,
        api_key_id=None,
    )
    if record is None:
        return None
    _require_catalog_record_authority(record, file_id=file_id, user_id=user_id)
    return record


def _close_managed_file_descriptor(managed: ManagedFileDescriptor) -> None:
    os.close(managed.descriptor)


async def open_verified_soai_file_descriptor(
    storage_root: str,
    *,
    record: FileCatalogRecordWithPath,
    attachment: JSONDict,
) -> ManagedFileDescriptor:
    file_id = attachment.get("file_id")
    owner_user_id = attachment.get("user_id")
    if not isinstance(file_id, str) or not file_id:
        raise ValidationError("SoAI file catalog id is missing.")
    if not is_strict_int(owner_user_id):
        raise ValidationError("SoAI file owner is invalid.")
    _require_catalog_record_authority(
        record,
        file_id=file_id,
        user_id=owner_user_id,
    )
    managed = await run_joined_thread_call(
        open_managed_file_descriptor,
        storage_root,
        record["file_path"],
        task_name="webui-attachment-file-open",
        cancelled_result_cleanup=_close_managed_file_descriptor,
    )
    completed = False
    try:
        if managed.size_bytes != record["size_bytes"] or managed.size_bytes != attachment.get(
            "size_bytes",
        ):
            raise FileStorageSecurityError("SoAI file size changed.")
        try:
            content_hash = await run_joined_thread_call(
                hash_descriptor_content,
                managed.descriptor,
                task_name="webui-attachment-file-hash",
            )
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
        return managed
    finally:
        if not completed:
            os.close(managed.descriptor)
