"""SoAI - Filesystem file-handle sync helpers [backend/core/filesystem/file_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os

__all__ = ("flush_and_fsync_file",)


def flush_and_fsync_file(file_handle: io.IOBase) -> None:
    file_handle.flush()
    os.fsync(file_handle.fileno())
