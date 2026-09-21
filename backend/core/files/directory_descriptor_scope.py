"""SoAI - Secure directory descriptor lifetime [backend/core/files/directory_descriptor_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from core.errors.exceptions import StateError
from core.files.secure_open_flags import secure_read_only_open_flags

__all__ = ("open_secure_directory_descriptor",)


@contextmanager
def open_secure_directory_descriptor(
    path: str,
    *,
    unsupported_message: str,
) -> Generator[int]:
    if os.name == "nt":
        raise StateError(unsupported_message)
    descriptor = os.open(path, secure_read_only_open_flags(directory=True))
    try:
        yield descriptor
    finally:
        os.close(descriptor)
