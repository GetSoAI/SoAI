"""SoAI - File explorer directory listing and metadata queries [backend/features/file_explorer/entry_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import heapq
import os
import stat

from core.bootstrap.files import compute_sha256
from core.errors.exceptions import NotFoundError, SecurityError, StateError
from core.files.directory_size import calculate_directory_size_bytes
from core.files.explorer_models import FileEntryInfo, FileMetadata, ListDirectoryResult
from features.file_explorer.entry_metadata import build_file_entry_info
from features.file_explorer.internal_protocols import SecureFileOpsProtocol
from features.file_explorer.mime import (
    classify_file_entry_type,
    detect_mime_type,
    file_entry_type_sort_rank,
)
from features.file_explorer.mime_content_refine import (
    MIME_CONTENT_SAMPLE_BYTES,
    OCTET_STREAM_CONTENT_TYPE,
    refine_octet_stream_mime,
)

__all__ = (
    "build_file_metadata",
    "build_list_directory_result",
)


def build_list_directory_result(
    *,
    secure_ops: SecureFileOpsProtocol,
    real_path: str,
    virtual_path: str,
    offset: int,
    limit: int,
) -> ListDirectoryResult:
    raw_entries = secure_ops.list_directory(real_path)
    total = len(raw_entries)
    end_index = offset + limit
    if total and 0 < end_index < total:
        selected = heapq.nsmallest(end_index, raw_entries)
        page = selected[offset:end_index]
    else:
        raw_entries.sort()
        page = raw_entries[offset:end_index]
    entries: list[FileEntryInfo] = []
    for entry_name in page:
        try:
            entry_stat = secure_ops.stat_entry(real_path, entry_name)
        except (NotFoundError, OSError):
            continue
        is_dir = stat.S_ISDIR(entry_stat.st_mode)
        entries.append(build_file_entry_info(entry_name, entry_stat, is_dir))
    return ListDirectoryResult(
        path=virtual_path,
        entries=entries,
        total=total,
        offset=offset,
        limit=limit,
    )


def build_file_metadata(
    *,
    secure_ops: SecureFileOpsProtocol,
    real_path: str,
    virtual_path: str,
    include_hash: bool,
) -> FileMetadata:
    entry_stat = secure_ops.stat_path(real_path)
    is_dir = stat.S_ISDIR(entry_stat.st_mode)
    name = os.path.basename(real_path) or "/"
    mime = detect_mime_type(name, is_dir)
    if not is_dir and mime == OCTET_STREAM_CONTENT_TYPE:
        try:
            sample = secure_ops.read_bytes_sample(real_path, max_bytes=MIME_CONTENT_SAMPLE_BYTES)
        except (NotFoundError, SecurityError, StateError, OSError):
            sample = b""
        mime = refine_octet_stream_mime(name, mime, sample)
    type_id = classify_file_entry_type(name, mime, is_directory=is_dir)
    perm_str = stat.filemode(entry_stat.st_mode)
    sha256_hash: str | None = None
    if include_hash and not is_dir:
        sha256_hash = compute_sha256(real_path)
    size = calculate_directory_size_bytes(real_path) if is_dir else entry_stat.st_size
    return FileMetadata(
        name=name,
        path=virtual_path,
        is_directory=is_dir,
        size=size,
        modified_at_ms=int(entry_stat.st_mtime_ns // 1_000_000),
        mime_type=mime,
        type_id=type_id,
        type_rank=file_entry_type_sort_rank(type_id),
        permissions=perm_str,
        sha256=sha256_hash,
    )
