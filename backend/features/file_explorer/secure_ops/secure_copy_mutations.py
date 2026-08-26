"""SoAI - Secure copy mutations [backend/features/file_explorer/secure_ops/secure_copy_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import NotFoundError, SecurityError, ValidationError
from core.filesystem.open_files import open_binary
from core.hardware.reserved_writes import write_reserved_bytes
from features.file_explorer.secure_ops.copy_error_coercion import (
    raise_copy_directory_exception,
    raise_copy_file_exception,
)
from features.file_explorer.secure_ops.copy_temp_directory import (
    allocate_copy_temp_directory,
)
from features.file_explorer.secure_ops.link_checks import (
    is_linkish_path,
)
from features.file_explorer.secure_ops.posix_copy_ops import (
    copy_directory_no_symlinks_posix,
    copy_file_no_symlinks_posix,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = (
    "copy_directory",
    "copy_file",
)

SECURE_COPY_CHUNK_BYTES = MIB_BYTES


def _require_destination_parent_directory(destination_path: str, *, operation: str) -> None:
    parent_dir = os.path.dirname(destination_path) or "."
    if os.path.isdir(parent_dir):
        return
    if os.path.exists(parent_dir):
        raise ValidationError(
            "Destination parent path is not a directory.",
            operation=operation,
        )
    raise NotFoundError(
        "Destination parent directory does not exist.",
        operation=operation,
    )


def _copy_file_no_overwrite(
    source_path: str,
    destination_path: str,
    *,
    follow_symlinks: bool,
    write_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> None:
    with (
        open_binary(source_path, mode="rb") as source_stream,
        open_binary(destination_path, mode="xb") as dest_stream,
    ):
        while True:
            data = source_stream.read(SECURE_COPY_CHUNK_BYTES)
            if not data:
                break
            write_reserved_bytes(dest_stream, data, reservation=write_reservation)
    shutil.copystat(source_path, destination_path, follow_symlinks=follow_symlinks)


def _commit_temp_file_no_overwrite(temp_file_path: str, destination_path: str) -> None:
    if os.name == "nt":
        os.rename(temp_file_path, destination_path)
        return
    os.link(temp_file_path, destination_path)
    os.unlink(temp_file_path)


def _copy_file_for_copytree(
    source_path: str,
    destination_path: str,
    *,
    follow_symlinks: bool,
    write_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> str:
    _copy_file_no_overwrite(
        source_path,
        destination_path,
        follow_symlinks=follow_symlinks,
        write_reservation=write_reservation,
    )
    return destination_path


def _copy_directory_no_symlinks_windows(
    source_path: str,
    destination_path: str,
    *,
    write_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> None:
    _require_destination_parent_directory(
        destination_path,
        operation="file_explorer.copy_directory",
    )
    temp_path = ""
    try:
        temp_path = allocate_copy_temp_directory(
            destination_path,
            operation="file_explorer.copy_directory",
            mode=None,
        )
        for dirpath, dirnames, filenames in os.walk(source_path, topdown=True, followlinks=False):
            if is_linkish_path(dirpath) and os.path.normcase(dirpath) != os.path.normcase(
                source_path,
            ):
                display_path = os.path.relpath(dirpath, source_path)
                raise SecurityError(
                    f"Cannot copy directory containing symlink: '{display_path}'.",
                    operation="file_explorer.copy_directory",
                )
            rel_dir = os.path.relpath(dirpath, source_path)
            if rel_dir == ".":
                dest_dir = temp_path
            else:
                dest_dir = os.path.join(temp_path, rel_dir)
                os.mkdir(dest_dir)
            for dirname in dirnames:
                entry_path = os.path.join(dirpath, dirname)
                if is_linkish_path(entry_path):
                    display_path = os.path.relpath(entry_path, source_path)
                    raise SecurityError(
                        f"Cannot copy directory containing symlink: '{display_path}'.",
                        operation="file_explorer.copy_directory",
                    )
            for filename in filenames:
                entry_path = os.path.join(dirpath, filename)
                if is_linkish_path(entry_path):
                    display_path = os.path.relpath(entry_path, source_path)
                    raise SecurityError(
                        f"Cannot copy directory containing symlink: '{display_path}'.",
                        operation="file_explorer.copy_directory",
                    )
                _copy_file_no_overwrite(
                    entry_path,
                    os.path.join(dest_dir, filename),
                    follow_symlinks=False,
                    write_reservation=write_reservation,
                )
            shutil.copystat(dirpath, dest_dir, follow_symlinks=False)
        os.replace(temp_path, destination_path)
    finally:
        if temp_path and os.path.lexists(temp_path):
            shutil.rmtree(temp_path)


def copy_file(
    source_path: str,
    destination_path: str,
    *,
    allow_symlinks: bool,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> None:
    if os.path.lexists(destination_path):
        raise ValidationError(
            "Destination path already exists.",
            operation="file_explorer.copy_file",
        )
    _require_destination_parent_directory(
        destination_path,
        operation="file_explorer.copy_file",
    )
    if not allow_symlinks and os.path.islink(source_path):
        raise SecurityError(
            "Cannot copy symbolic link.",
            operation="file_explorer.copy_file",
        )
    if not os.path.isfile(source_path):
        raise NotFoundError(
            f"Source file not found: '{os.path.basename(source_path)}'.",
            operation="file_explorer.copy_file",
        )
    temp_path = ""
    try:
        temp_path = allocate_copy_temp_directory(
            destination_path,
            operation="file_explorer.copy_file",
            mode=0o700,
        )
        temp_file_path = os.path.join(temp_path, os.path.basename(destination_path))
        if os.name != "nt" and not allow_symlinks:
            copy_file_no_symlinks_posix(
                source_path,
                temp_file_path,
                write_reservation=write_reservation,
            )
        else:
            _copy_file_no_overwrite(
                source_path,
                temp_file_path,
                follow_symlinks=allow_symlinks,
                write_reservation=write_reservation,
            )
        _commit_temp_file_no_overwrite(temp_file_path, destination_path)
    except OSError as exception:
        raise_copy_file_exception(
            exception,
            source_path=source_path,
            operation="file_explorer.copy_file",
            os_error_message="Failed to copy file.",
        )
    finally:
        if temp_path and os.path.lexists(temp_path):
            shutil.rmtree(temp_path)


def copy_directory(
    source_path: str,
    destination_path: str,
    *,
    allow_symlinks: bool,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> None:
    if os.path.lexists(destination_path):
        raise ValidationError(
            "Destination path already exists.",
            operation="file_explorer.copy_directory",
        )
    _require_destination_parent_directory(
        destination_path,
        operation="file_explorer.copy_directory",
    )
    if not os.path.isdir(source_path):
        raise NotFoundError(
            f"Source directory not found: '{os.path.basename(source_path)}'.",
            operation="file_explorer.copy_directory",
        )
    if os.name == "nt" and not allow_symlinks:
        if is_linkish_path(source_path):
            raise SecurityError(
                "Cannot copy symbolic link.",
                operation="file_explorer.copy_directory",
            )
        try:
            _copy_directory_no_symlinks_windows(
                source_path,
                destination_path,
                write_reservation=write_reservation,
            )
        except OSError as exception:
            raise_copy_directory_exception(
                exception,
                operation="file_explorer.copy_directory",
                not_found_message="Source or destination parent not found.",
                os_error_message="Failed to copy directory.",
            )
        return
    if os.name != "nt" and not allow_symlinks:
        if os.path.islink(source_path):
            raise SecurityError(
                "Cannot copy symbolic link.",
                operation="file_explorer.copy_directory",
            )
        copy_directory_no_symlinks_posix(
            source_path,
            destination_path,
            write_reservation=write_reservation,
        )
        return
    try:
        shutil.copytree(
            source_path,
            destination_path,
            symlinks=allow_symlinks,
            copy_function=lambda source_file, destination_file: _copy_file_for_copytree(
                source_file,
                destination_file,
                follow_symlinks=allow_symlinks,
                write_reservation=write_reservation,
            ),
        )
    except OSError as exception:
        raise_copy_directory_exception(
            exception,
            operation="file_explorer.copy_directory",
            not_found_message=(f"Source directory not found: '{os.path.basename(source_path)}'."),
            os_error_message="Failed to copy directory.",
        )
