"""SoAI - Chunked transfer staging and hashing [backend/core/files/staged_transfer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Callable, Iterable, Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass

from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.filesystem.open_files import open_binary
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger

__all__ = (
    "STAGED_TRANSFER_CHUNK_SIZE",
    "StagedTransferResult",
    "compute_file_sha256",
    "iter_reader_chunks",
    "stage_chunks_to_temp_file",
)

OPERATION_CORE_FILES_STAGED_TRANSFER_CLEANUP_STAGED_FILE = (
    "core.files.staged_transfer.cleanup_staged_file"
)


LOGGER_NAME = "SoAI.core.files.staged_transfer"


STAGED_TRANSFER_CHUNK_SIZE = MIB_BYTES


@dataclass(frozen=True, slots=True)
class StagedTransferResult:
    file_path: str
    size_bytes: int
    sha256_hex: str


def _coerce_chunk(raw_chunk: bytes | bytearray | memoryview) -> bytes:
    if isinstance(raw_chunk, bytes):
        return raw_chunk
    if isinstance(raw_chunk, bytearray):
        return bytes(raw_chunk)
    if isinstance(raw_chunk, memoryview):
        return raw_chunk.tobytes()
    raise ValidationError(f"Chunk source produced non-bytes data: {type(raw_chunk).__name__}")


def iter_reader_chunks(
    read_chunk: Callable[[int], bytes | bytearray | memoryview],
    *,
    chunk_size: int = STAGED_TRANSFER_CHUNK_SIZE,
) -> Iterator[bytes]:
    if chunk_size <= 0:
        raise ValidationError("chunk_size must be a positive integer.")
    while True:
        raw_chunk = read_chunk(chunk_size)
        if not raw_chunk:
            break
        yield _coerce_chunk(raw_chunk)


def _cleanup_staged_file(path: str, operation: str, logger: StandardLogger) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to remove staged transfer temp file (non-critical).",
            operation=OPERATION_CORE_FILES_STAGED_TRANSFER_CLEANUP_STAGED_FILE,
            details={"path": path, "cleanup_operation": operation},
            level="debug",
        )


def stage_chunks_to_temp_file(
    chunks: Iterable[bytes | bytearray | memoryview],
    *,
    temp_dir: str,
    suffix: str,
    on_chunk_write_scope: Callable[[int], AbstractContextManager[None]],
    on_chunk_written: Callable[[int], None] | None = None,
    max_bytes: int | None = None,
    expected_size: int | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> StagedTransferResult:
    logger = get_logger(LOGGER_NAME)
    total_bytes = 0
    digest = hashlib.sha256()
    temp_file_path: str | None = None
    staging_complete = False
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=suffix) as temp_file:
            temp_file_path = temp_file.name
            for raw_chunk in chunks:
                chunk = _coerce_chunk(raw_chunk)
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if max_bytes is not None and total_bytes > max_bytes:
                    raise PayloadTooLargeError(
                        f"Transfer exceeds the configured limit of {max_bytes} bytes.",
                    )
                if expected_size is not None and total_bytes > expected_size:
                    raise ValidationError("Transfer size exceeded the declared size limit.")
                write_scope = on_chunk_write_scope(len(chunk))
                with write_scope:
                    temp_file.write(chunk)
                    digest.update(chunk)
                    if on_chunk_written is not None:
                        on_chunk_written(len(chunk))
                if on_progress is not None:
                    on_progress(total_bytes)
            temp_file.flush()
            if expected_size is not None and total_bytes != expected_size:
                raise ValidationError("Transfer size mismatch.")
        result = StagedTransferResult(
            file_path=temp_file_path,
            size_bytes=total_bytes,
            sha256_hex=digest.hexdigest().lower(),
        )
        staging_complete = True
        return result
    finally:
        if not staging_complete and temp_file_path is not None:
            _cleanup_staged_file(
                temp_file_path,
                "core.files.staged_transfer.stage_chunks_to_temp_file.cleanup",
                logger,
            )


def compute_file_sha256(
    file_path: str,
    *,
    chunk_size: int = STAGED_TRANSFER_CHUNK_SIZE,
) -> StagedTransferResult:
    if chunk_size <= 0:
        raise ValidationError("chunk_size must be a positive integer.")
    digest = hashlib.sha256()
    total_bytes = 0
    with open_binary(file_path, mode="rb") as file_handle:
        while True:
            chunk = file_handle.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            digest.update(chunk)
    return StagedTransferResult(
        file_path=file_path,
        size_bytes=total_bytes,
        sha256_hex=digest.hexdigest().lower(),
    )
