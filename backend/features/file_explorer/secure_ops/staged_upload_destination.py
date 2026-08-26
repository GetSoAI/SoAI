"""SoAI - Pinned staged upload destination ownership [backend/features/file_explorer/secure_ops/staged_upload_destination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import SecurityError, ValidationError
from features.file_explorer.secure_ops.link_checks import is_no_symlink_open_error

__all__ = (
    "fsync_destination_directory",
    "open_pinned_destination_directory",
    "rollback_destination_entry",
)


def open_pinned_destination_directory(
    destination_root: str,
    destination_parent: str,
    *,
    allow_symlinks: bool,
) -> int:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY
    if allow_symlinks:
        return os.open(destination_parent, directory_flags)
    directory_flags |= os.O_NOFOLLOW
    root = os.path.abspath(destination_root)
    parent = os.path.abspath(destination_parent)
    current_descriptor = os.open(root, directory_flags)
    descriptor_returned = False
    try:
        relative_parent = os.path.relpath(parent, root)
        if relative_parent == ".":
            descriptor_returned = True
            return current_descriptor
        for path_component in relative_parent.split(os.sep):
            try:
                next_descriptor = os.open(
                    path_component,
                    directory_flags,
                    dir_fd=current_descriptor,
                )
            except OSError as exception:
                component_stat = os.stat(
                    path_component,
                    dir_fd=current_descriptor,
                    follow_symlinks=False,
                )
                if stat.S_ISLNK(component_stat.st_mode) or is_no_symlink_open_error(exception):
                    raise SecurityError(
                        "Upload destination contains a symbolic link."
                    ) from exception
                if not stat.S_ISDIR(component_stat.st_mode):
                    raise ValidationError(
                        "Upload destination parent path is not a directory."
                    ) from exception
                raise
            previous_descriptor = current_descriptor
            current_descriptor = next_descriptor
            os.close(previous_descriptor)
        descriptor_returned = True
        return current_descriptor
    finally:
        if not descriptor_returned:
            os.close(current_descriptor)


def rollback_destination_entry(destination_name: str, destination_descriptor: int) -> None:
    os.unlink(destination_name, dir_fd=destination_descriptor)
    fsync_destination_directory(destination_descriptor)


def fsync_destination_directory(directory_descriptor: int) -> None:
    os.fsync(directory_descriptor)
