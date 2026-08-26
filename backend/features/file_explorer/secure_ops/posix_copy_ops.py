"""SoAI - POSIX copy operations for secure file explorer mutations [backend/features/file_explorer/secure_ops/posix_copy_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import stat
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import NotFoundError, SecurityError, StateError, ValidationError
from core.hardware.reserved_writes import write_reserved_bytes
from features.file_explorer.secure_ops.copy_error_coercion import (
    raise_copy_directory_exception,
    raise_copy_file_exception,
)
from features.file_explorer.secure_ops.copy_temp_directory import (
    allocate_copy_temp_directory,
)
from features.file_explorer.secure_ops.link_checks import is_no_symlink_open_error

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = (
    "copy_directory_no_symlinks_posix",
    "copy_file_no_symlinks_posix",
)

_COPY_FILE_BUFFER_BYTES = MIB_BYTES


def _copy_file_descriptor_to_path(
    source_fd: int,
    *,
    destination_path: str,
    destination_stat: os.stat_result,
    write_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> None:
    dest_fd = -1
    try:
        open_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        dest_fd = os.open(destination_path, open_flags, int(destination_stat.st_mode) & 0o777)
        with (
            os.fdopen(source_fd, "rb", closefd=False) as source_stream,
            os.fdopen(
                dest_fd,
                "wb",
                closefd=False,
            ) as dest_stream,
        ):
            while True:
                data = source_stream.read(_COPY_FILE_BUFFER_BYTES)
                if not data:
                    break
                write_reserved_bytes(dest_stream, data, reservation=write_reservation)
            os.fchmod(dest_fd, int(destination_stat.st_mode) & 0o777)
            os.utime(
                dest_fd,
                ns=(
                    int(destination_stat.st_atime_ns),
                    int(destination_stat.st_mtime_ns),
                ),
            )
    finally:
        if dest_fd >= 0:
            os.close(dest_fd)


def copy_file_no_symlinks_posix(
    source_path: str,
    destination_path: str,
    *,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> None:
    src_fd = -1
    try:
        src_fd = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
        st = os.fstat(src_fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValidationError(
                "Unsupported source file type.",
                operation="file_explorer.copy_file",
            )
        try:
            _copy_file_descriptor_to_path(
                src_fd,
                destination_path=destination_path,
                destination_stat=st,
                write_reservation=write_reservation,
            )
        except FileNotFoundError as exception:
            raise NotFoundError(
                "Destination parent directory does not exist.",
                operation="file_explorer.copy_file",
            ) from exception
    except (FileNotFoundError, FileExistsError) as exception:
        raise_copy_file_exception(
            exception,
            source_path=source_path,
            operation="file_explorer.copy_file",
            os_error_message="Failed to open source file for copy.",
        )
    except OSError as exception:
        if is_no_symlink_open_error(exception):
            raise SecurityError(
                "Cannot copy symbolic link.",
                operation="file_explorer.copy_file",
            ) from exception
        raise_copy_file_exception(
            exception,
            source_path=source_path,
            operation="file_explorer.copy_file",
            os_error_message="Failed to open source file for copy.",
        )
    finally:
        if src_fd >= 0:
            os.close(src_fd)


def _copy_file_no_symlinks_posix_from_dir_fd(
    dir_fd: int,
    *,
    filename: str,
    destination_path: str,
    write_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> None:
    src_fd = -1
    try:
        src_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
        st = os.fstat(src_fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValidationError(
                "Unsupported source file type.",
                operation="file_explorer.copy_directory",
            )
        try:
            _copy_file_descriptor_to_path(
                src_fd,
                destination_path=destination_path,
                destination_stat=st,
                write_reservation=write_reservation,
            )
        except FileNotFoundError as exception:
            raise NotFoundError(
                "Destination parent directory does not exist.",
                operation="file_explorer.copy_directory",
            ) from exception
    except FileNotFoundError as exception:
        raise NotFoundError(
            f"Source file not found: '{filename}'.",
            operation="file_explorer.copy_directory",
        ) from exception
    except FileExistsError as exception:
        raise ValidationError(
            "Destination path already exists.",
            operation="file_explorer.copy_directory",
        ) from exception
    except OSError as exception:
        if is_no_symlink_open_error(exception):
            raise SecurityError(
                "Cannot copy symbolic link.",
                operation="file_explorer.copy_directory",
            ) from exception
        raise StateError(
            "Failed to open source file for directory copy.",
            operation="file_explorer.copy_directory",
        ) from exception
    finally:
        if src_fd >= 0:
            os.close(src_fd)


def copy_directory_no_symlinks_posix(
    source_path: str,
    destination_path: str,
    *,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> None:
    temp_path = ""
    try:
        temp_path = allocate_copy_temp_directory(
            destination_path,
            operation="file_explorer.copy_directory",
            mode=0o700,
        )
        for dirpath, dirnames, filenames, dir_fd in os.fwalk(
            source_path,
            follow_symlinks=False,
        ):
            rel_dir = os.path.relpath(dirpath, source_path)
            if rel_dir == ".":
                dest_dir = temp_path
            else:
                dest_dir = os.path.join(temp_path, rel_dir)
                os.mkdir(dest_dir, 0o700)
            for dirname in dirnames:
                st = os.lstat(dirname, dir_fd=dir_fd)
                if stat.S_ISLNK(st.st_mode):
                    display_path = os.path.join(rel_dir, dirname)
                    message = f"Cannot copy directory containing symlink: '{display_path}'."
                    raise SecurityError(
                        message,
                        operation="file_explorer.copy_directory",
                    )
            for filename in filenames:
                st = os.lstat(filename, dir_fd=dir_fd)
                if stat.S_ISLNK(st.st_mode):
                    display_path = os.path.join(rel_dir, filename)
                    message = f"Cannot copy directory containing symlink: '{display_path}'."
                    raise SecurityError(
                        message,
                        operation="file_explorer.copy_directory",
                    )
                dest_file = os.path.join(dest_dir, filename)
                _copy_file_no_symlinks_posix_from_dir_fd(
                    dir_fd,
                    filename=filename,
                    destination_path=dest_file,
                    write_reservation=write_reservation,
                )
            shutil.copystat(dirpath, dest_dir, follow_symlinks=False)
        os.replace(temp_path, destination_path)
    except (FileNotFoundError, FileExistsError) as exception:
        raise_copy_directory_exception(
            exception,
            operation="file_explorer.copy_directory",
            not_found_message="Source or destination parent not found.",
            os_error_message="Failed to copy directory.",
        )
    finally:
        if temp_path and os.path.lexists(temp_path):
            shutil.rmtree(temp_path)
