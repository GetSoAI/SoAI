"""SoAI - Staged upload descriptor copy I/O [backend/features/file_explorer/secure_ops/staged_upload_copy_io.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError

__all__ = ("write_all",)


def write_all(file_descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(file_descriptor, data[offset:])
        if written <= 0:
            raise StateError("Failed to write staged upload copy.")
        offset += written
