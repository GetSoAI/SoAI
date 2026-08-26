"""SoAI - WebUI conversation attachment file catalog access [backend/features/api/routes/webui/conversation_attachments/file_catalog_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_constants import WEBUI_CHAT_ATTACHMENT_PURPOSE
from core.errors.exceptions import ConflictError

if TYPE_CHECKING:
    from core.files.database_types import FileCatalogRecordWithPath
    from core.files.protocols import DatabaseFilesProtocol
    from core.types.json import JSONDict

__all__ = ("get_attachment_file_catalog_record",)


async def get_attachment_file_catalog_record(
    *,
    database_files: DatabaseFilesProtocol,
    attachment: JSONDict,
    user_id: int,
) -> FileCatalogRecordWithPath:
    file_id = str(attachment.get("file_id") or "")
    if not file_id:
        raise ConflictError("Attachment file_id is invalid.")
    file_record = await database_files.get_file_info_with_path(
        file_id,
        enforce_owner=True,
        user_id=user_id,
        api_key_id=None,
    )
    if file_record is None:
        raise ConflictError("Attachment file catalog row is missing.")
    if file_record["purpose"] != WEBUI_CHAT_ATTACHMENT_PURPOSE:
        raise ConflictError("Attachment file purpose is invalid.")
    if file_record["api_key_id"] is not None:
        raise ConflictError("Attachment file ownership is invalid.")
    return file_record
