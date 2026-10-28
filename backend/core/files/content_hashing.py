"""SoAI - File content hashing helpers [backend/core/files/content_hashing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.files.descriptor_reading import read_descriptor_at
from core.filesystem.descriptor_io import open_descriptor
from core.validation.strict_numbers import require_non_negative_int_strict

if TYPE_CHECKING:
    from core.concurrency.deadlines import MonotonicDeadline
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "ContentHashResult",
    "hash_descriptor_content",
    "hash_file_content",
    "hash_seekable_binary_stream_content",
)

_HASH_CHUNK_BYTES = MIB_BYTES


@dataclass(frozen=True, slots=True)
class ContentHashResult:
    size_bytes: int
    sha256_hex: str


def hash_seekable_binary_stream_content(
    stream: io.BufferedIOBase | io.RawIOBase,
) -> ContentHashResult:
    digest = hashlib.sha256()
    total_bytes = 0
    try:
        stream.seek(0)
        while True:
            chunk = stream.read(_HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            total_bytes += len(chunk)
    except (OSError, ValueError) as exception:
        raise ValidationError("File content could not be hashed.") from exception
    return ContentHashResult(size_bytes=total_bytes, sha256_hex=digest.hexdigest().lower())


def hash_descriptor_content(
    descriptor: int,
    *,
    maximum_bytes: int | None = None,
    cancellation: CancellationTokenProtocol | None = None,
    deadline: MonotonicDeadline | None = None,
) -> ContentHashResult:
    if maximum_bytes is not None:
        require_non_negative_int_strict(
            maximum_bytes, error_message="Hash byte limit must be nonnegative."
        )
    digest = hashlib.sha256()
    total_bytes = 0
    offset = 0
    while True:
        if deadline is not None and deadline.expired():
            raise TimeoutError("File verification exceeded its operation deadline.")
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        try:
            read_size = (
                _HASH_CHUNK_BYTES
                if maximum_bytes is None
                else min(_HASH_CHUNK_BYTES, maximum_bytes - total_bytes + 1)
            )
            chunk = read_descriptor_at(descriptor, read_size, offset)
        except TimeoutError:
            raise
        except OSError as exception:
            raise ValidationError("File content could not be hashed.") from exception
        if not chunk:
            break
        digest.update(chunk)
        total_bytes += len(chunk)
        if maximum_bytes is not None and total_bytes > maximum_bytes:
            raise ValidationError("File content grew beyond the accepted byte limit.")
        offset += len(chunk)
    return ContentHashResult(size_bytes=total_bytes, sha256_hex=digest.hexdigest().lower())


def hash_file_content(file_path: str) -> ContentHashResult:
    try:
        descriptor = open_descriptor(file_path, os.O_RDONLY)
    except OSError as exception:
        raise ValidationError("File content could not be hashed.") from exception
    try:
        return hash_descriptor_content(descriptor)
    except OSError as exception:
        raise ValidationError("File content could not be hashed.") from exception
    finally:
        os.close(descriptor)
