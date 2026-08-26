"""SoAI - Shared file-entry metadata construction [backend/features/file_explorer/entry_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.files.explorer_models import FileEntryInfo
from features.file_explorer.mime import (
    classify_file_entry_type,
    detect_mime_type,
    file_entry_type_sort_rank,
)

__all__ = ("build_file_entry_info",)


def build_file_entry_info(
    entry_name: str,
    entry_stat: os.stat_result,
    is_directory: bool,
) -> FileEntryInfo:
    entry_size = 0 if is_directory else entry_stat.st_size
    mime_type = detect_mime_type(entry_name, is_directory)
    type_id = classify_file_entry_type(
        entry_name,
        mime_type,
        is_directory=is_directory,
    )
    return FileEntryInfo(
        name=entry_name,
        is_directory=is_directory,
        size=entry_size,
        modified_at_ms=int(entry_stat.st_mtime_ns // 1_000_000),
        mime_type=mime_type,
        type_id=type_id,
        type_rank=file_entry_type_sort_rank(type_id),
        permissions=stat.filemode(entry_stat.st_mode),
    )
