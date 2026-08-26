"""SoAI - POSIX directory fd utilities for secure ops [backend/features/file_explorer/secure_ops/fd_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import NotFoundError, StateError, ValidationError

__all__ = ("open_directory_fd",)


def open_directory_fd(path: str) -> int:
    if os.name == "nt":
        raise StateError(
            "File descriptor operations not supported on Windows.",
            operation="file_explorer.open_directory",
        )
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError as exception:
        raise NotFoundError(
            f"Directory not found: '{os.path.basename(path)}'.",
            operation="file_explorer.open_directory",
        ) from exception
    except NotADirectoryError as exception:
        raise ValidationError(
            f"Path is not a directory: '{os.path.basename(path)}'.",
        ) from exception
    try:
        st = os.fstat(directory_fd)
        if not stat.S_ISDIR(st.st_mode):
            os.close(directory_fd)
            raise ValidationError(
                f"Path is not a directory: '{os.path.basename(path)}'.",
                operation="file_explorer.open_directory",
            )
    except OSError as exception:
        os.close(directory_fd)
        raise StateError(
            "Failed to validate opened directory.",
            operation="file_explorer.open_directory",
        ) from exception
    return directory_fd
