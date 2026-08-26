"""SoAI - Secure temporary files for network downloads [backend/core/network/download_temp_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os

from core.errors.exceptions import ValidationError
from core.files.temp_files import create_secure_temp_file_descriptor

__all__ = ("create_download_temp_handle",)


def create_download_temp_handle(destination_path: str) -> tuple[io.BufferedWriter, str]:
    destination_dir = os.path.dirname(os.path.abspath(destination_path)) or None
    file_descriptor, temp_path = create_secure_temp_file_descriptor(
        directory=destination_dir,
        prefix=".soai_download_",
        suffix=".part",
    )
    try:
        handle = os.fdopen(file_descriptor, "wb")
    except (OSError, ValueError) as open_exception:
        try:
            os.close(file_descriptor)
        except OSError as close_exception:
            open_exception.add_note(
                f"Download temp file descriptor cleanup failed: {close_exception}",
            )
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError as remove_exception:
                open_exception.add_note(f"Download temp file cleanup failed: {remove_exception}")
        raise
    if not isinstance(handle, io.BufferedWriter):
        handle.close()
        os.remove(temp_path)
        raise ValidationError("Failed to open temporary download file for writing.")
    return handle, temp_path
