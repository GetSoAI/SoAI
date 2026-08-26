"""SoAI - Secure read-only filesystem open flags [backend/core/files/secure_open_flags.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.files.managed_storage_errors import FileStorageSecurityError

__all__ = ("secure_read_only_open_flags",)


def secure_read_only_open_flags(*, directory: bool) -> int:
    try:
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
        if directory:
            flags |= os.O_DIRECTORY
        return flags
    except AttributeError as exception:
        raise FileStorageSecurityError(
            "Secure no-follow filesystem opens are unavailable on this platform.",
        ) from exception
