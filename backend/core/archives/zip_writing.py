"""SoAI - Secure ZIP archive writing and cleanup [backend/core/archives/zip_writing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from threading import Event
from zipfile import ZIP_DEFLATED, ZipFile

from core.archives.zip_creation_models import (
    ZipArchiveDirectory,
    ZipArchivePlan,
    ZipArchiveResult,
)
from core.archives.zip_member_writing import build_zip_info, write_regular_zip_file
from core.concurrency.cancellation import check_cancellation_deadline
from core.concurrency.deadlines import MonotonicDeadline
from core.errors.exceptions import SecurityError, StateError
from core.files.directory_snapshot import (
    verify_directory_snapshot,
)
from core.files.file_identity import FileIdentity
from core.files.path_policy import ensure_path_within_base_lexical
from core.files.temp_files import create_secure_temp_binary_handle
from core.filesystem.file_sync import flush_and_fsync_file

__all__ = ("write_zip_archive", "remove_completed_zip_archive")


def write_zip_archive(
    *,
    plan: ZipArchivePlan,
    root_path: str,
    temp_directory: str,
    cancellation_event: Event,
    deadline: MonotonicDeadline | None = None,
    operation: str = "file_explorer.download_archive",
    prefix: str = "soai-file-explorer-",
) -> ZipArchiveResult:
    check_cancellation_deadline(cancellation_event, deadline, operation=operation)
    file_handle, archive_path = create_secure_temp_binary_handle(
        directory=temp_directory,
        prefix=prefix,
        suffix=".zip",
    )
    initial_status: os.stat_result | None = None
    completed = False
    try:
        with file_handle:
            initial_status = os.fstat(file_handle.fileno())
            with ZipFile(
                file_handle,
                mode="w",
                compression=ZIP_DEFLATED,
                allowZip64=True,
                strict_timestamps=False,
            ) as archive:
                for entry in plan.entries:
                    check_cancellation_deadline(cancellation_event, deadline, operation=operation)
                    if entry.is_directory:
                        archive.writestr(build_zip_info(entry), b"")
                    else:
                        write_regular_zip_file(
                            archive,
                            entry,
                            root_path=root_path,
                            cancellation_event=cancellation_event,
                            deadline=deadline,
                            operation=operation,
                        )
                _verify_directories(
                    plan.directories,
                    root_path=root_path,
                    cancellation_event=cancellation_event,
                    deadline=deadline,
                    operation=operation,
                )
            check_cancellation_deadline(cancellation_event, deadline, operation=operation)
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
                operation=f"{operation}.write",
            )
        check_cancellation_deadline(cancellation_event, deadline, operation=operation)
        result = ZipArchiveResult(
            archive_path=archive_path,
            download_filename=plan.download_filename,
            identity=FileIdentity.from_stat(archive_status),
        )
        completed = True
        return result
    except OSError as exception:
        raise StateError(
            "File explorer download archive could not be written.",
            operation=f"{operation}.write",
            cause=exception,
        ) from exception
    finally:
        if not completed and initial_status is not None:
            _remove_incomplete_archive(
                archive_path,
                expected_device=int(initial_status.st_dev),
                expected_inode=int(initial_status.st_ino),
                primary_exception=sys.exception(),
            )


def _verify_directories(
    directories: tuple[ZipArchiveDirectory, ...],
    *,
    root_path: str,
    cancellation_event: Event,
    deadline: MonotonicDeadline | None = None,
    operation: str = "file_explorer.download_archive",
) -> None:
    for directory in directories:
        check_cancellation_deadline(cancellation_event, deadline, operation=operation)
        validated_path = ensure_path_within_base_lexical(
            root_path,
            directory.source_path,
            description="File explorer archive directory",
            error_cls=SecurityError,
        )
        verify_directory_snapshot(
            root_path,
            validated_path,
            expected_identity=directory.identity,
            expected_child_names=directory.child_names,
            cancellation_event=cancellation_event,
            deadline=deadline,
            operation=f"{operation}.verify",
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


def remove_completed_zip_archive(result: ZipArchiveResult) -> None:
    try:
        current_status = os.lstat(result.archive_path)
        if FileIdentity.from_stat(current_status) != result.identity:
            return
        os.remove(result.archive_path)
    except FileNotFoundError:
        return
