"""SoAI - Cross-platform positioned descriptor reads [backend/core/files/descriptor_reading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

__all__ = ("read_descriptor_at",)


_WINDOWS_BINARY_FILE_MODE = 0x8000


if sys.platform == "win32":
    import msvcrt

    def _set_binary_mode(descriptor: int) -> None:
        msvcrt.setmode(descriptor, _WINDOWS_BINARY_FILE_MODE)

else:

    def _set_binary_mode(descriptor: int) -> None:
        _ = descriptor


def _read_descriptor_at_windows(descriptor: int, size: int, offset: int) -> bytes:
    _set_binary_mode(descriptor)
    original_offset = os.lseek(descriptor, 0, os.SEEK_CUR)
    try:
        os.lseek(descriptor, offset, os.SEEK_SET)
        return os.read(descriptor, size)
    finally:
        os.lseek(descriptor, original_offset, os.SEEK_SET)


def read_descriptor_at(descriptor: int, size: int, offset: int) -> bytes:
    if os.name == "nt":
        return _read_descriptor_at_windows(descriptor, size, offset)
    return os.pread(descriptor, size, offset)
