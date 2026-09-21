"""SoAI - WebUI conversation attachment file catalog access [backend/features/api/routes/webui/conversation_attachments/file_catalog_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, ValidationError
from features.api.runtime.webui_attachments.physical_file_snapshot import (
    load_soai_file_record,
)

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
    file_id = attachment.get("file_id")
    if not isinstance(file_id, str) or not file_id:
        raise ConflictError("Attachment file_id is invalid.")
    try:
        file_record = await load_soai_file_record(
            database_files,
            user_id=user_id,
            attachment=attachment,
        )
    except ValidationError as exception:
        raise ConflictError(str(exception)) from exception
    if file_record is None:
        raise ConflictError("Attachment file catalog row is missing.")
    return file_record
