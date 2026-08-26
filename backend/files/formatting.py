"""SoAI - OpenAI file object formatting [backend/files/formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_files import FileStatus
from files.types import FileRecord

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("format_openai_file_object",)


def format_openai_file_object(file_record: FileRecord) -> JSONDict:
    return {
        "id": file_record["id"],
        "object": "file",
        "bytes": file_record["size_bytes"],
        "created_at": file_record["created_at"],
        "filename": file_record["filename"],
        "purpose": file_record["purpose"],
        "status": file_record.get("status", FileStatus.UPLOADED.value),
        "status_details": file_record.get("status_details"),
    }
