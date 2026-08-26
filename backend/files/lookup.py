"""SoAI - File info database lookup [backend/files/lookup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import NotFoundError
from core.files.protocols import DatabaseFilesProtocol
from core.timing.durations import ms_to_seconds_floor
from files.types import FileRecord

__all__ = ("get_file_info_or_fail",)


async def get_file_info_or_fail(
    database_files: DatabaseFilesProtocol,
    file_id: str,
    *,
    with_path: bool = False,
    enforce_owner: bool = False,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> FileRecord:
    record = (
        await database_files.get_file_info_with_path(
            file_id,
            enforce_owner=enforce_owner,
            user_id=user_id,
            api_key_id=api_key_id,
        )
        if with_path
        else await database_files.get_file_info(
            file_id,
            enforce_owner=enforce_owner,
            user_id=user_id,
            api_key_id=api_key_id,
        )
    )
    if not record:
        raise NotFoundError(f"File with ID '{file_id}' not found.")
    created_at_ms = record["created_at_ms"]
    created_at = ms_to_seconds_floor(int(created_at_ms))
    file_record: FileRecord = {
        "id": record["id"],
        "filename": record["filename"],
        "purpose": record["purpose"],
        "size_bytes": record["size_bytes"],
        "created_at": created_at,
        "status": record["status"],
        "status_details": record.get("status_details"),
    }
    if with_path:
        file_path = record.get("file_path")
        if isinstance(file_path, str) and file_path:
            file_record["file_path"] = file_path
    return file_record
