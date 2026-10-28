"""SoAI - Core filesystem hashing utilities [backend/core/filesystem/hashing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import hashlib
import os
import threading
from collections.abc import Callable
from functools import partial

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.file_identity import FileIdentity
from core.files.staged_transfer import iter_reader_chunks
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.filesystem.path_coercion import normalize_filesystem_path
from core.filesystem.protocols import CancellableHashCalculationProtocol
from core.logging.trace import get_logger

__all__ = (
    "calculate_directory_hash",
    "calculate_file_hash",
    "calculate_file_hash_sync",
)

LOGGER_NAME = "SoAI.core.filesystem.hashing"
OPERATION_PLUGIN_SDK_FILESYSTEM_HASHING_CALCULATE_DIRECTORY_HASH_SYNC = (
    "plugin_sdk.filesystem.hashing.calculate_directory_hash_sync"
)
OPERATION_PLUGIN_SDK_FILESYSTEM_HASHING_CALCULATE_FILE_HASH_SYNC = (
    "plugin_sdk.filesystem.hashing.calculate_file_hash_sync"
)


DIRECTORY_HASH_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
)


def calculate_file_hash_sync(
    file_path: str, *, cancellation_check: Callable[[], None] | None = None
) -> str | None:
    file_path = normalize_filesystem_path(file_path)
    if os.path.islink(file_path):
        return None
    if not os.path.isfile(file_path):
        return None
    hasher = hashlib.sha256()
    file_hash: str | None = None
    try:
        with open_regular_binary_no_symlink(file_path) as handle:
            identity = FileIdentity.from_stat(os.fstat(handle.fileno()))
            for chunk in iter_reader_chunks(handle.read):
                if cancellation_check is not None:
                    cancellation_check()
                hasher.update(chunk)
            if not identity.matches_descriptor_snapshot(
                FileIdentity.from_stat(os.fstat(handle.fileno()))
            ):
                raise ValidationError("File changed while calculating its checksum.")
        file_hash = hasher.hexdigest()
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Could not hash file (non-critical).",
            operation=OPERATION_PLUGIN_SDK_FILESYSTEM_HASHING_CALCULATE_FILE_HASH_SYNC,
            details={"file_path": file_path},
            level="debug",
        )
        file_hash = None
    return file_hash


def _calculate_directory_hash_sync(
    dir_path: str, *, cancellation_check: Callable[[], None]
) -> str | None:
    dir_path = normalize_filesystem_path(dir_path)
    dir_hash: str | None = None
    try:
        dir_hasher = hashlib.sha256()
        for root, dirs, filenames in os.walk(dir_path):
            cancellation_check()
            dirs.sort()
            sorted_filenames = sorted(filenames)
            relative_root = os.path.relpath(root, dir_path).replace(os.sep, "/")
            dir_hasher.update(b"D")
            dir_hasher.update(relative_root.encode("utf-8"))
            dir_hasher.update(b"\0")
            for name in sorted_filenames:
                if name.startswith(".soai"):
                    continue
                full_path = os.path.join(root, name)
                file_hash = calculate_file_hash_sync(
                    full_path,
                    cancellation_check=cancellation_check,
                )
                if not file_hash:
                    continue
                relative = os.path.relpath(full_path, dir_path).replace(os.sep, "/")
                dir_hasher.update(b"F")
                dir_hasher.update(relative.encode("utf-8"))
                dir_hasher.update(b"\0")
                dir_hasher.update(file_hash.encode("ascii"))
                dir_hasher.update(b"\0")
        dir_hash = dir_hasher.hexdigest()
    except DIRECTORY_HASH_OPERATION_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Could not hash directory (non-critical).",
            operation=OPERATION_PLUGIN_SDK_FILESYSTEM_HASHING_CALCULATE_DIRECTORY_HASH_SYNC,
            details={"dir_path": dir_path},
            level="debug",
        )
        dir_hash = None
    return dir_hash


async def _run_cancellable_hash(
    calculate_hash: CancellableHashCalculationProtocol,
    path: str,
    *,
    task_name: str,
) -> str | None:
    cancellation = threading.Event()

    def raise_if_cancelled() -> None:
        if cancellation.is_set():
            raise asyncio.CancelledError("Hash calculation was cancelled.")

    return await run_joined_thread_call(
        partial(calculate_hash, path, cancellation_check=raise_if_cancelled),
        task_name=task_name,
        retain_resources_until_complete=True,
        on_cancel=cancellation.set,
    )


async def calculate_file_hash(file_path: str) -> str | None:
    return await _run_cancellable_hash(
        calculate_file_hash_sync,
        os.path.abspath(file_path),
        task_name="core-filesystem-file-hash",
    )


async def calculate_directory_hash(dir_path: str) -> str | None:
    dir_path = normalize_filesystem_path(os.path.abspath(dir_path))
    if not await asyncio.to_thread(os.path.isdir, dir_path):
        return None
    return await _run_cancellable_hash(
        _calculate_directory_hash_sync,
        dir_path,
        task_name="core-filesystem-directory-hash",
    )
