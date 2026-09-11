"""SoAI - Release artifact file validation and bounded reading [backend/app/updater/release_artifact_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary

__all__ = ("read_bounded_release_file", "require_regular_release_file")


def require_regular_release_file(path: str, *, label: str) -> os.stat_result:
    try:
        file_stat = os.stat(path, follow_symlinks=False)
    except OSError as exception:
        raise ValidationError(f"{label} is missing or unreadable.") from exception
    if not stat.S_ISREG(file_stat.st_mode) or os.path.islink(path):
        raise ValidationError(f"{label} must be a regular file.")
    return file_stat


def read_bounded_release_file(path: str, *, maximum_bytes: int, label: str) -> bytes:
    file_stat = require_regular_release_file(path, label=label)
    if file_stat.st_size <= 0 or file_stat.st_size > maximum_bytes:
        raise ValidationError(f"{label} has an invalid size.")
    try:
        with open_binary(path, mode="rb") as file_handle:
            content = file_handle.read(maximum_bytes + 1)
    except OSError as exception:
        raise ValidationError(f"{label} is missing or unreadable.") from exception
    if len(content) != file_stat.st_size:
        raise ValidationError(f"{label} changed while it was being read.")
    return content
