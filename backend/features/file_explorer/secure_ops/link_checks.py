"""SoAI - Link-type checks for secure file operations [backend/features/file_explorer/secure_ops/link_checks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import ntpath
import os

__all__ = (
    "is_linkish_path",
    "is_no_symlink_open_error",
)


def is_linkish_path(path: str) -> bool:
    if os.path.islink(path):
        return True
    if os.name != "nt":
        return False
    return bool(ntpath.isjunction(path))


def is_no_symlink_open_error(exception: OSError) -> bool:
    error_number = exception.errno
    if error_number is None:
        return False
    if error_number == errno.ELOOP:
        return True
    if errno.errorcode.get(error_number) == "EMLINK":
        return True
    if errno.errorcode.get(error_number) == "EFTYPE":
        return True
    return False
