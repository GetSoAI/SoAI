"""SoAI - Binary descriptor opens, complete writes and bounded reads [backend/core/filesystem/descriptor_io.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import stat
import sys

from core.errors.exceptions import StateError, ValidationError
from core.validation.integers import is_strict_int

__all__ = (
    "open_descriptor",
    "open_text_descriptor",
    "write_all_descriptor_bytes",
    "read_exclusive_regular_descriptor",
    "read_bounded_descriptor",
)


def open_text_descriptor(
    descriptor: int,
    *,
    mode: str,
    encoding: str,
    errors: str,
    newline: str | None = None,
    error_type: type[Exception] = ValidationError,
    error_message: str = "Descriptor text reader or writer failed to open a text stream.",
) -> io.TextIOBase:
    try:
        handle = os.fdopen(descriptor, mode, encoding=encoding, errors=errors, newline=newline)
    except (OSError, ValueError):
        os.close(descriptor)
        raise
    if not isinstance(handle, io.TextIOBase):
        handle.close()
        raise error_type(error_message)
    return handle


def open_descriptor(
    path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
    flags: int,
    mode: int = 0o777,
    *,
    dir_fd: int | None = None,
) -> int:
    if sys.platform == "win32":
        flags |= os.O_BINARY
    return os.open(path, flags, mode, dir_fd=dir_fd)


def write_all_descriptor_bytes(descriptor: int, content: bytes, *, error_message: str) -> None:
    remaining = memoryview(content)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError(error_message)
        remaining = remaining[written:]


def read_exclusive_regular_descriptor(descriptor: int, maximum_bytes: int) -> bytes:
    if not is_strict_int(maximum_bytes) or maximum_bytes < 0:
        raise ValidationError("Bounded file reads require a nonnegative byte limit.")
    information = os.fstat(descriptor)
    if not stat.S_ISREG(information.st_mode) or information.st_nlink != 1:
        raise StateError("Materialized member is not an exclusive regular file.")
    if information.st_size > maximum_bytes:
        raise StateError("Materialized member exceeds its accepted size.")
    return read_bounded_descriptor(
        descriptor,
        maximum_bytes,
        error_message="Materialized member changed beyond its accepted size.",
    )


def read_bounded_descriptor(descriptor: int, maximum_bytes: int, *, error_message: str) -> bytes:
    if not is_strict_int(maximum_bytes) or maximum_bytes < 0:
        raise ValidationError("Bounded file reads require a nonnegative byte limit.")
    pieces: list[bytes] = []
    total = 0
    while total <= maximum_bytes:
        piece = os.read(descriptor, min(65536, maximum_bytes + 1 - total))
        if not piece:
            return b"".join(pieces)
        total += len(piece)
        pieces.append(piece)
    raise StateError(error_message)
