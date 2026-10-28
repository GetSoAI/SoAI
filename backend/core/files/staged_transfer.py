"""SoAI - Chunked transfer staging and hashing [backend/core/files/staged_transfer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import io
import os
import sys
from collections.abc import Callable, Iterable, Iterator
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import PayloadTooLargeError, SoAIError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.anchored_directory import (
    open_anchored_workspace,
    require_anchored_directory_identity,
)
from core.files.commit_receipt import FileCleanupIncompleteError
from core.files.content_hashing import ContentHashResult
from core.files.temp_files import create_secure_temp_binary_handle
from core.files.windows_handle_operations import mark_windows_file_descriptor_for_deletion
from core.filesystem.descriptor_io import write_all_descriptor_bytes
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.open_files import open_binary
from core.logging.trace import get_logger
from core.platform.os import is_windows
from core.validation.strict_numbers import require_non_negative_int_strict

if TYPE_CHECKING:
    from core.files.protocols_anchored import AnchoredDirectoryProtocol

__all__ = (
    "STAGED_TRANSFER_CHUNK_SIZE",
    "StagedTransferResult",
    "compute_file_sha256",
    "cleanup_staged_file",
    "iter_reader_chunks",
    "stage_chunks_to_temp_file",
    "write_chunks_to_descriptor",
)

LOGGER_NAME = "SoAI.core.files.staged_transfer"
OPERATION_CORE_FILES_STAGED_TRANSFER_CLEANUP_STAGED_FILE = (
    "core.files.staged_transfer.cleanup_staged_file"
)

STAGED_TRANSFER_CHUNK_SIZE = MIB_BYTES

_STAGING_CLEANUP_PUBLIC_MESSAGE = (
    "The operation failed and temporary file cleanup could not be completed. "
    "Contact an administrator if storage remains occupied."
)


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


def cleanup_staged_file(
    path: str,
    *,
    descriptor: int,
    directory_authority: AnchoredDirectoryProtocol,
    directory_identity: tuple[int, int],
) -> None:
    try:
        if directory_authority.identity != directory_identity:
            raise FileCleanupIncompleteError("The staged file directory identity changed.")
        if not is_windows():
            raise FileCleanupIncompleteError(
                "The staged file was retained without atomic identity-bound deletion authority."
            )
        mark_windows_file_descriptor_for_deletion(descriptor)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failure = FileCleanupIncompleteError(
            "Temporary file cleanup could not be completed safely.",
            cause=exception,
            details={
                "cleanup_incomplete": True,
                "retained_paths": [path],
                "directory_identity": list(directory_identity),
            },
        )
        failure.public_message = _STAGING_CLEANUP_PUBLIC_MESSAGE
        failure.public_details = {"cleanup_incomplete": True}
        raise failure from exception


def write_chunks_to_descriptor(
    descriptor: int,
    chunks: Iterable[bytes | bytearray | memoryview],
    *,
    on_chunk_write_scope: Callable[[int], AbstractContextManager[None]],
    on_chunk_written: Callable[[int], None] | None = None,
    max_bytes: int | None = None,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> ContentHashResult:
    if max_bytes is not None:
        require_non_negative_int_strict(max_bytes, error_message="max_bytes must be nonnegative.")
    if expected_size is not None:
        require_non_negative_int_strict(
            expected_size, error_message="expected_size must be nonnegative."
        )
    total_bytes = 0
    digest = hashlib.sha256()
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
            write_all_descriptor_bytes(
                descriptor,
                chunk,
                error_message="Staged file write made no progress.",
            )
            digest.update(chunk)
            if on_chunk_written is not None:
                on_chunk_written(len(chunk))
        if on_progress is not None:
            on_progress(total_bytes)
    if expected_size is not None and total_bytes != expected_size:
        raise ValidationError("Transfer size mismatch.")
    if expected_sha256 is not None and digest.hexdigest() != expected_sha256:
        raise ValidationError("Transfer content does not match its expected SHA-256.")
    return ContentHashResult(size_bytes=total_bytes, sha256_hex=digest.hexdigest())


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
    expected_sha256: str | None = None,
    durability: Literal["temporary", "file", "directory"] = "temporary",
    directory_authority: AnchoredDirectoryProtocol | None = None,
    verify_source_content: Callable[[ContentHashResult], None] | None = None,
) -> StagedTransferResult:
    if max_bytes is not None:
        require_non_negative_int_strict(max_bytes, error_message="max_bytes must be nonnegative.")
    if expected_size is not None:
        require_non_negative_int_strict(
            expected_size, error_message="expected_size must be nonnegative."
        )
    if durability not in {"temporary", "file", "directory"}:
        raise ValidationError("Unsupported staged file durability requirement.")
    temp_file_path: str | None = None
    temp_file: io.BufferedRandom | None = None
    staging_directory = (
        os.path.abspath(temp_dir) if durability == "directory" else os.path.realpath(temp_dir)
    )
    with (
        open_anchored_workspace(staging_directory)
        if directory_authority is None
        else nullcontext(directory_authority)
    ) as anchored:
        directory_identity = anchored.identity
        try:
            temp_file, temp_file_path = create_secure_temp_binary_handle(
                directory=staging_directory,
                prefix="soai-transfer-",
                suffix=suffix,
                directory_authority=anchored,
                delete_access=is_windows(),
            )
            content = write_chunks_to_descriptor(
                temp_file.fileno(),
                chunks,
                on_chunk_write_scope=on_chunk_write_scope,
                on_chunk_written=on_chunk_written,
                max_bytes=max_bytes,
                expected_size=expected_size,
                expected_sha256=expected_sha256,
                on_progress=on_progress,
            )
            temp_file.flush()
            if durability != "temporary":
                flush_and_fsync_file(temp_file)
            if verify_source_content is not None:
                verify_source_content(content)
            require_anchored_directory_identity(staging_directory, directory_identity)
            if durability == "directory":
                anchored.flush()
            return StagedTransferResult(
                file_path=temp_file_path,
                size_bytes=content.size_bytes,
                sha256_hex=content.sha256_hex,
            )
        finally:
            primary = sys.exception()
            cleanup_failure: FileCleanupIncompleteError | None = None
            if temp_file is not None:
                try:
                    if primary is not None and temp_file_path is not None:
                        cleanup_staged_file(
                            temp_file_path,
                            descriptor=temp_file.fileno(),
                            directory_authority=anchored,
                            directory_identity=directory_identity,
                        )
                except FileCleanupIncompleteError as exception:
                    cleanup_failure = exception
                finally:
                    try:
                        temp_file.close()
                    except HANDLED_RUNTIME_EXCEPTIONS as exception:
                        if cleanup_failure is not None:
                            cleanup_failure.add_note(f"Staged file close failed: {exception}")
                        else:
                            cleanup_failure = FileCleanupIncompleteError(
                                "The staged file could not be closed.",
                                cause=exception,
                                details={
                                    "cleanup_incomplete": True,
                                    "retained_paths": [temp_file_path],
                                },
                            )
                            cleanup_failure.public_message = _STAGING_CLEANUP_PUBLIC_MESSAGE
                            cleanup_failure.public_details = {"cleanup_incomplete": True}
            if cleanup_failure is not None:
                if primary is None:
                    raise cleanup_failure from cleanup_failure.__cause__
                if isinstance(primary, SoAIError):
                    if not primary.public_message:
                        primary.public_message = _STAGING_CLEANUP_PUBLIC_MESSAGE
                    primary.details = {
                        **(cleanup_failure.details or {}),
                        **(primary.details or {}),
                        "cleanup_incomplete": True,
                        "staging_cleanup": dict(cleanup_failure.details or {}),
                    }
                    primary.public_details = {
                        **(primary.public_details or {}),
                        "cleanup_incomplete": True,
                    }
                primary.add_note(str(cleanup_failure))
                if primary.__cause__ is None:
                    cleanup_cause: BaseException | None = cleanup_failure
                    visited_causes: set[int] = set()
                    while cleanup_cause is not None and id(cleanup_cause) not in visited_causes:
                        visited_causes.add(id(cleanup_cause))
                        if cleanup_cause.__context__ is primary:
                            cleanup_cause.__context__ = None
                        cleanup_cause = cleanup_cause.__cause__
                    primary.__cause__ = cleanup_failure
                    if isinstance(primary, SoAIError):
                        primary.cause = cleanup_failure
                log_handled_exception(
                    get_logger(LOGGER_NAME),
                    cleanup_failure,
                    message="Incomplete staged file cleanup requires reconciliation.",
                    operation=OPERATION_CORE_FILES_STAGED_TRANSFER_CLEANUP_STAGED_FILE,
                    details=cleanup_failure.details,
                    level="warning",
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
