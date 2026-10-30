"""SoAI - Secure ZIP member serialization [backend/core/archives/zip_member_writing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import time
from calendar import monthrange
from threading import Event
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from core.archives.constants import CHUNK_READ_SIZE
from core.archives.zip_creation_models import (
    ZipArchiveEntry,
)
from core.concurrency.cancellation import check_cancellation_deadline
from core.concurrency.deadlines import MonotonicDeadline
from core.errors.exceptions import ConflictError, SecurityError, StateError
from core.files.file_identity import FileIdentity
from core.files.managed_file_opening import open_managed_file_descriptor
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.managed_storage_traversal import close_file_descriptor_stack
from core.files.path_policy import ensure_path_within_base_lexical

__all__ = ("build_zip_info", "write_regular_zip_file")


def write_regular_zip_file(
    archive: ZipFile,
    entry: ZipArchiveEntry,
    *,
    root_path: str,
    cancellation_event: Event,
    deadline: MonotonicDeadline | None = None,
    operation: str = "file_explorer.download_archive",
) -> None:
    validated_path = ensure_path_within_base_lexical(
        root_path,
        entry.source_path,
        description="File explorer archive source",
        error_cls=SecurityError,
    )
    try:
        managed_file = open_managed_file_descriptor(root_path, validated_path)
    except FileStorageSecurityError as exception:
        if isinstance(exception.__cause__, FileNotFoundError):
            raise ConflictError(
                "File explorer download source changed during archive creation.",
                operation=f"{operation}.write",
            ) from exception
        raise SecurityError(
            "File explorer download source failed secure traversal.",
            operation=f"{operation}.write",
        ) from exception
    try:
        opened_source = os.fdopen(managed_file.descriptor, "rb")
    except (OSError, ValueError) as exception:
        close_file_descriptor_stack(
            [managed_file.descriptor],
            primary_exception=exception,
        )
        raise StateError(
            "File explorer download source descriptor could not be opened.",
            operation=f"{operation}.write",
            cause=exception,
        ) from exception
    with opened_source:
        if not isinstance(opened_source, io.BufferedReader):
            opened_source.close()
            raise StateError(
                "File explorer download source did not open as a buffered binary file.",
                operation=f"{operation}.write",
            )
        source = opened_source
        opened_identity = FileIdentity.from_stat(os.fstat(source.fileno()))
        _require_identity(entry.identity, opened_identity, entry.archive_path, operation)
        with archive.open(build_zip_info(entry), mode="w", force_zip64=True) as destination:
            remaining_bytes = entry.identity.size
            while remaining_bytes > 0:
                check_cancellation_deadline(cancellation_event, deadline, operation=operation)
                data = source.read(min(CHUNK_READ_SIZE, remaining_bytes))
                if not data:
                    raise ConflictError(
                        "File explorer download source shrank during archive creation.",
                        operation=f"{operation}.write",
                    )
                written = destination.write(data)
                if written != len(data):
                    raise StateError(
                        "ZIP archive writer did not consume the complete source chunk.",
                        operation=f"{operation}.write",
                    )
                remaining_bytes -= len(data)
                check_cancellation_deadline(cancellation_event, deadline, operation=operation)
            if source.read(1):
                raise ConflictError(
                    "File explorer download source grew during archive creation.",
                    operation=f"{operation}.write",
                )
        final_identity = FileIdentity.from_stat(os.fstat(source.fileno()))
        _require_identity(opened_identity, final_identity, entry.archive_path, operation)


def _require_identity(
    expected: FileIdentity,
    actual: FileIdentity,
    display_path: str,
    operation: str,
) -> None:
    if expected.matches_descriptor_snapshot(actual):
        return
    raise ConflictError(
        f"File explorer download source changed during archive creation: '{display_path}'.",
        operation=f"{operation}.verify",
    )


def build_zip_info(entry: ZipArchiveEntry) -> ZipInfo:
    zip_info = ZipInfo(
        filename=entry.archive_path,
        date_time=_zip_timestamp(entry.identity.modified_ns),
    )
    zip_info.compress_type = ZIP_DEFLATED
    zip_info.create_system = 3
    zip_info.external_attr = (entry.identity.mode & 0xFFFF) << 16
    if entry.is_directory:
        zip_info.external_attr |= 0x10
    return zip_info


def _zip_timestamp(modified_ns: int) -> tuple[int, int, int, int, int, int]:
    try:
        timestamp = time.localtime(modified_ns / 1_000_000_000)
    except (OSError, OverflowError, ValueError):
        return (1980, 1, 1, 0, 0, 0)
    year = min(2107, max(1980, timestamp.tm_year))
    return (
        year,
        timestamp.tm_mon,
        min(timestamp.tm_mday, monthrange(year, timestamp.tm_mon)[1]),
        timestamp.tm_hour,
        timestamp.tm_min,
        timestamp.tm_sec,
    )
