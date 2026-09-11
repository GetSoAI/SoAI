"""SoAI - Filesystem file-handle sync helpers [backend/core/filesystem/file_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os

from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.open_files import open_regular_file_descriptor_no_symlink
from core.filesystem.path_coercion import normalize_filesystem_path

__all__ = ("flush_and_fsync_file", "fsync_install_entry")


def flush_and_fsync_file(file_handle: io.IOBase) -> None:
    file_handle.flush()
    os.fsync(file_handle.fileno())


def _fsync_regular_file(path: str) -> None:
    descriptor = open_regular_file_descriptor_no_symlink(path, writable=os.name == "nt")
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fsync_install_entry(path: str) -> None:
    path = normalize_filesystem_path(path)
    if os.path.islink(path):
        fsync_directory(os.path.dirname(path), strict=True)
        return
    if not os.path.isdir(path):
        _fsync_regular_file(path)
        fsync_directory(os.path.dirname(path), strict=True)
        return
    for directory, _, filenames in os.walk(path, topdown=False, followlinks=False):
        for filename in filenames:
            file_path = os.path.join(directory, filename)
            if os.path.islink(file_path):
                continue
            _fsync_regular_file(file_path)
        fsync_directory(directory, strict=True)
    fsync_directory(os.path.dirname(path), strict=True)
