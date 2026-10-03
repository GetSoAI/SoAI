"""SoAI - Atomic file publication without replacement [backend/core/filesystem/exclusive_rename.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import errno
import os

from core.filesystem.path_coercion import coerce_path, normalize_filesystem_path
from core.platform.os import is_linux, is_macos, is_windows

__all__ = ("rename_file_without_replacement",)

_LINUX_CURRENT_DIRECTORY = -100
_LINUX_RENAME_NOREPLACE = 1
_MACOS_RENAME_EXCL = 4


def rename_file_without_replacement(source: str, destination: str) -> None:
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
            _LINUX_CURRENT_DIRECTORY,
            os.fsencode(source_path),
            _LINUX_CURRENT_DIRECTORY,
            os.fsencode(destination_path),
            _LINUX_RENAME_NOREPLACE,
        )
    elif is_macos():
        rename = library.renamex_np
        rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(source_path), os.fsencode(destination_path), _MACOS_RENAME_EXCL)
    else:
        raise OSError(errno.ENOTSUP, "Atomic exclusive rename is unavailable on this platform.")
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), source, None, destination)
