"""SoAI - File content hashing helpers [backend/core/files/content_hashing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.files.descriptor_reading import read_descriptor_at

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


def hash_descriptor_content(descriptor: int) -> ContentHashResult:
    digest = hashlib.sha256()
    total_bytes = 0
    offset = 0
    while True:
        try:
            chunk = read_descriptor_at(descriptor, _HASH_CHUNK_BYTES, offset)
        except OSError as exception:
            raise ValidationError("File content could not be hashed.") from exception
        if not chunk:
            break
        digest.update(chunk)
        total_bytes += len(chunk)
        offset += len(chunk)
    return ContentHashResult(size_bytes=total_bytes, sha256_hex=digest.hexdigest().lower())


def hash_file_content(file_path: str) -> ContentHashResult:
    try:
        descriptor = os.open(file_path, os.O_RDONLY)
    except OSError as exception:
        raise ValidationError("File content could not be hashed.") from exception
    try:
        return hash_descriptor_content(descriptor)
    except OSError as exception:
        raise ValidationError("File content could not be hashed.") from exception
    finally:
        os.close(descriptor)
