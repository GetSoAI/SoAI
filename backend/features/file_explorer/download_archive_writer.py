"""SoAI - Secure file explorer ZIP archive writer [backend/features/file_explorer/download_archive_writer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import sys
import time
from threading import Event
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from core.archives.constants import CHUNK_READ_SIZE
from core.errors.exceptions import ConflictError, SecurityError, StateError
from core.files.explorer_models import FileExplorerDownloadArchive
from core.files.file_identity import FileIdentity
from core.files.managed_file_opening import open_managed_file_descriptor
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.managed_storage_traversal import close_file_descriptor_stack
from core.files.path_policy import ensure_path_within_base_lexical
from core.files.temp_files import create_secure_temp_binary_handle
from core.filesystem.file_sync import flush_and_fsync_file
from features.file_explorer.download_archive_cancellation import (
    raise_if_download_archive_cancelled,
)
from features.file_explorer.download_archive_directory_access import (
    verify_download_directory,
)
from features.file_explorer.download_archive_models import (
    DownloadArchiveDirectory,
    DownloadArchiveEntry,
    DownloadArchivePlan,
)

__all__ = ("write_download_archive",)


def write_download_archive(
    *,
    plan: DownloadArchivePlan,
    root_path: str,
    temp_directory: str,
    cancellation_event: Event,
) -> FileExplorerDownloadArchive:
    file_handle, archive_path = create_secure_temp_binary_handle(
        directory=temp_directory,
        prefix="soai-file-explorer-",
        suffix=".zip",
    )
    initial_status = os.fstat(file_handle.fileno())
    completed = False
    try:
        with file_handle:
            with ZipFile(
                file_handle,
                mode="w",
                compression=ZIP_DEFLATED,
                allowZip64=True,
                strict_timestamps=False,
            ) as archive:
                for entry in plan.entries:
                    raise_if_download_archive_cancelled(cancellation_event)
                    if entry.is_directory:
                        archive.writestr(_build_zip_info(entry), b"")
                    else:
                        _write_regular_file(
                            archive,
                            entry,
                            root_path=root_path,
                            cancellation_event=cancellation_event,
                        )
                _verify_directories(
                    plan.directories,
                    root_path=root_path,
                    cancellation_event=cancellation_event,
                )
            flush_and_fsync_file(file_handle)
            archive_status = os.fstat(file_handle.fileno())
            size_bytes = int(archive_status.st_size)
        if size_bytes > plan.required_bytes:
            raise StateError(
                "ZIP archive exceeded its validated disk reservation.",
                details={
                    "required_bytes": plan.required_bytes,
                    "actual_bytes": size_bytes,
                },
                operation="file_explorer.download_archive.write",
            )
        completed = True
        return FileExplorerDownloadArchive(
            archive_path=archive_path,
            download_filename=plan.download_filename,
            identity=FileIdentity.from_stat(archive_status),
        )
    except OSError as exception:
        raise StateError(
            "File explorer download archive could not be written.",
            operation="file_explorer.download_archive.write",
            cause=exception,
        ) from exception
    finally:
        if not completed:
            _remove_incomplete_archive(
                archive_path,
                expected_device=int(initial_status.st_dev),
                expected_inode=int(initial_status.st_ino),
                primary_exception=sys.exception(),
            )


def _write_regular_file(
    archive: ZipFile,
    entry: DownloadArchiveEntry,
    *,
    root_path: str,
    cancellation_event: Event,
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
                operation="file_explorer.download_archive.write",
            ) from exception
        raise SecurityError(
            "File explorer download source failed secure traversal.",
            operation="file_explorer.download_archive.write",
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
            operation="file_explorer.download_archive.write",
            cause=exception,
        ) from exception
    with opened_source:
        if not isinstance(opened_source, io.BufferedReader):
            opened_source.close()
            raise StateError(
                "File explorer download source did not open as a buffered binary file.",
                operation="file_explorer.download_archive.write",
            )
        source = opened_source
        opened_identity = FileIdentity.from_stat(os.fstat(source.fileno()))
        _require_identity(entry.identity, opened_identity, entry.archive_path)
        with archive.open(_build_zip_info(entry), mode="w", force_zip64=True) as destination:
            remaining_bytes = entry.identity.size
            while remaining_bytes > 0:
                raise_if_download_archive_cancelled(cancellation_event)
                data = source.read(min(CHUNK_READ_SIZE, remaining_bytes))
                if not data:
                    raise ConflictError(
                        "File explorer download source shrank during archive creation.",
                        operation="file_explorer.download_archive.write",
                    )
                written = destination.write(data)
                if written != len(data):
                    raise StateError(
                        "ZIP archive writer did not consume the complete source chunk.",
                        operation="file_explorer.download_archive.write",
                    )
                remaining_bytes -= len(data)
            if source.read(1):
                raise ConflictError(
                    "File explorer download source grew during archive creation.",
                    operation="file_explorer.download_archive.write",
                )
        final_identity = FileIdentity.from_stat(os.fstat(source.fileno()))
        _require_descriptor_identity(opened_identity, final_identity, entry.archive_path)


def _verify_directories(
    directories: tuple[DownloadArchiveDirectory, ...],
    *,
    root_path: str,
    cancellation_event: Event,
) -> None:
    for directory in directories:
        raise_if_download_archive_cancelled(cancellation_event)
        validated_path = ensure_path_within_base_lexical(
            root_path,
            directory.source_path,
            description="File explorer archive directory",
            error_cls=SecurityError,
        )
        verify_download_directory(
            root_path,
            validated_path,
            expected_identity=directory.identity,
            expected_child_names=directory.child_names,
        )


def _require_identity(
    expected: FileIdentity,
    actual: FileIdentity,
    display_path: str,
) -> None:
    if actual == expected:
        return
    raise ConflictError(
        f"File explorer download source changed during archive creation: '{display_path}'.",
        operation="file_explorer.download_archive.verify",
    )


def _require_descriptor_identity(
    expected: FileIdentity,
    actual: FileIdentity,
    display_path: str,
) -> None:
    if expected.matches_descriptor_snapshot(actual):
        return
    raise ConflictError(
        f"File explorer download source changed during archive creation: '{display_path}'.",
        operation="file_explorer.download_archive.verify",
    )


def _build_zip_info(entry: DownloadArchiveEntry) -> ZipInfo:
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
        timestamp.tm_mday,
        timestamp.tm_hour,
        timestamp.tm_min,
        timestamp.tm_sec,
    )


def _remove_incomplete_archive(
    archive_path: str,
    *,
    expected_device: int,
    expected_inode: int,
    primary_exception: BaseException | None,
) -> None:
    try:
        current_status = os.lstat(archive_path)
        if (
            int(current_status.st_dev) != expected_device
            or int(current_status.st_ino) != expected_inode
        ):
            return
        os.remove(archive_path)
    except FileNotFoundError:
        return
    except OSError as cleanup_exception:
        if primary_exception is None:
            raise StateError(
                "Failed to remove incomplete file explorer download archive.",
                operation="file_explorer.download_archive.cleanup",
                cause=cleanup_exception,
            ) from cleanup_exception
        primary_exception.add_note(
            f"Incomplete download archive cleanup failed: {cleanup_exception}",
        )
