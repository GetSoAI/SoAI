"""SoAI - Secure file ops mutations [backend/features/file_explorer/secure_ops/secure_file_ops_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
import stat

from core.errors.exceptions import NotFoundError, SecurityError, ValidationError
from core.files.windows_readonly_deletion import (
    remove_file_with_readonly_support,
    remove_tree_with_readonly_support,
)
from features.file_explorer.secure_ops.fd_ops import open_directory_fd
from features.file_explorer.secure_ops.secure_copy_mutations import (
    copy_directory,
    copy_file,
)

__all__ = (
    "copy_directory",
    "copy_file",
    "create_directory",
    "move_entry",
    "remove_directory_recursive",
    "remove_file",
)


def create_directory(real_path: str) -> None:
    os.makedirs(real_path, exist_ok=True)


def remove_file(real_path: str, *, allow_symlinks: bool) -> None:
    if os.name == "nt":
        if not allow_symlinks and os.path.islink(real_path):
            raise SecurityError(
                "Cannot remove symbolic link.",
                operation="file_explorer.remove_file",
            )
        try:
            remove_file_with_readonly_support(real_path)
        except FileNotFoundError as exception:
            raise NotFoundError(
                f"File not found: '{os.path.basename(real_path)}'.",
                operation="file_explorer.remove_file",
            ) from exception
        except IsADirectoryError as exception:
            raise ValidationError(
                "Target is a directory, not a file.",
            ) from exception
        except PermissionError as exception:
            raise ValidationError(
                "File could not be removed because access was denied.",
                operation="file_explorer.remove_file",
            ) from exception
        return
    parent_dir = os.path.dirname(real_path)
    name = os.path.basename(real_path)
    dir_fd = open_directory_fd(parent_dir)
    try:
        if not allow_symlinks:
            st = os.lstat(name, dir_fd=dir_fd)
            if stat.S_ISLNK(st.st_mode):
                raise SecurityError(
                    "Cannot remove symbolic link.",
                    operation="file_explorer.remove_file",
                )
        os.unlink(name, dir_fd=dir_fd)
    except FileNotFoundError as exception:
        raise NotFoundError(
            f"File not found: '{name}'.",
            operation="file_explorer.remove_file",
        ) from exception
    except IsADirectoryError as exception:
        raise ValidationError(
            "Target is a directory, not a file.",
        ) from exception
    finally:
        os.close(dir_fd)


def remove_directory_recursive(real_path: str) -> None:
    if not os.path.isdir(real_path):
        raise NotFoundError(
            f"Directory not found: '{os.path.basename(real_path)}'.",
            operation="file_explorer.remove_directory",
        )
    remove_tree_with_readonly_support(real_path)


def move_entry(source_path: str, destination_path: str) -> None:
    if os.path.lexists(destination_path):
        raise ValidationError(
            "Destination path already exists.",
            operation="file_explorer.move_entry",
        )
    if os.name == "nt":
        try:
            os.rename(source_path, destination_path)
        except FileNotFoundError as exception:
            raise NotFoundError(
                "Source or destination parent not found.",
                operation="file_explorer.move_entry",
            ) from exception
        except OSError as exception:
            if exception.errno == errno.EXDEV:
                raise ValidationError(
                    "Cross-device moves are not supported. Copy the entry and delete the source.",
                    operation="file_explorer.move_entry",
                ) from exception
            raise ValidationError(
                "Failed to move entry.",
                operation="file_explorer.move_entry",
            ) from exception
        return
    src_parent = os.path.dirname(source_path)
    src_name = os.path.basename(source_path)
    dst_parent = os.path.dirname(destination_path)
    dst_name = os.path.basename(destination_path)

    src_dir_fd = open_directory_fd(src_parent)
    try:
        dst_dir_fd = open_directory_fd(dst_parent)
        try:
            os.rename(
                src_name,
                dst_name,
                src_dir_fd=src_dir_fd,
                dst_dir_fd=dst_dir_fd,
            )
        finally:
            os.close(dst_dir_fd)
    except FileNotFoundError as exception:
        raise NotFoundError(
            "Source or destination parent not found.",
            operation="file_explorer.move_entry",
        ) from exception
    finally:
        os.close(src_dir_fd)
