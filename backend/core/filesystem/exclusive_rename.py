"""SoAI - Atomic file publication without replacement [backend/core/filesystem/exclusive_rename.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import errno
import os

from core.errors.exceptions import ValidationError
from core.files.windows_entry_publication import rename_windows_directory_without_replacement
from core.filesystem.path_coercion import (
    coerce_path,
    normalize_filesystem_path,
    require_direct_entry_name,
)
from core.platform.os import is_linux, is_macos, is_windows
from core.validation.integers import is_strict_int

__all__ = ("rename_file_without_replacement",)

_LINUX_CURRENT_DIRECTORY = -100
_LINUX_RENAME_NOREPLACE = 1
_MACOS_RENAME_EXCL = 4


def rename_file_without_replacement(
    source: str,
    destination: str,
    *,
    source_dir_fd: int | None = None,
    destination_dir_fd: int | None = None,
    directory_handle: int | None = None,
) -> None:
    anchored = source_dir_fd is not None or destination_dir_fd is not None
    if directory_handle is not None:
        if (
            anchored
            or not is_windows()
            or not is_strict_int(directory_handle)
            or directory_handle < 0
        ):
            raise ValidationError(
                "Native directory publication requires one Windows parent handle."
            )
        rename_windows_directory_without_replacement(directory_handle, source, destination)
        return
    if anchored:
        if (
            not is_strict_int(source_dir_fd)
            or not is_strict_int(destination_dir_fd)
            or source_dir_fd < 0
            or destination_dir_fd < 0
        ):
            raise ValidationError("Exclusive anchored rename requires two directory descriptors.")
        for name in (source, destination):
            require_direct_entry_name(name)
        if is_windows():
            raise OSError(errno.ENOTSUP, "Windows publication requires native directory handles.")
    source_path = normalize_filesystem_path(coerce_path(source))
    destination_path = normalize_filesystem_path(coerce_path(destination))
    if is_windows():
        os.rename(source_path, destination_path)
        return
    library = ctypes.CDLL(None, use_errno=True)
    if is_linux():
        rename = library.renameat2
        rename.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int
        result = rename(
            source_dir_fd if source_dir_fd is not None else _LINUX_CURRENT_DIRECTORY,
            os.fsencode(source_path),
            destination_dir_fd if destination_dir_fd is not None else _LINUX_CURRENT_DIRECTORY,
            os.fsencode(destination_path),
            _LINUX_RENAME_NOREPLACE,
        )
    elif is_macos():
        if anchored:
            rename = library.renameatx_np
            rename.argtypes = (
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            )
            rename.restype = ctypes.c_int
            result = rename(
                source_dir_fd,
                os.fsencode(source_path),
                destination_dir_fd,
                os.fsencode(destination_path),
                _MACOS_RENAME_EXCL,
            )
        else:
            rename = library.renamex_np
            rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
            rename.restype = ctypes.c_int
            result = rename(
                os.fsencode(source_path), os.fsencode(destination_path), _MACOS_RENAME_EXCL
            )
    else:
        raise OSError(errno.ENOTSUP, "Atomic exclusive rename is unavailable on this platform.")
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), source, None, destination)
