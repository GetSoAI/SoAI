"""SoAI - OpenAI file object payload helpers [backend/core/openai/file_objects.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_files import FileStatus
from core.timing.durations import ms_to_seconds_floor

if TYPE_CHECKING:
    from core.files.database_types import FileCatalogRecord
    from core.types.json import JSONDict

__all__ = ("format_openai_file_object_from_catalog_record",)


def format_openai_file_object_from_catalog_record(db_record: FileCatalogRecord) -> JSONDict:
    status = db_record.get("status", FileStatus.UPLOADED.value)
    status_details = db_record.get("status_details")
    return {
        "id": db_record["id"],
        "object": "file",
        "bytes": db_record["size_bytes"],
        "created_at": ms_to_seconds_floor(int(db_record["created_at_ms"])),
        "filename": db_record["filename"],
        "purpose": db_record["purpose"],
        "status": status,
        "status_details": status_details,
    }
