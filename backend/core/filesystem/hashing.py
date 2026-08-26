"""SoAI - Core filesystem hashing utilities [backend/core/filesystem/hashing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import hashlib
import os

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
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


def calculate_file_hash_sync(file_path: str) -> str | None:
    if os.path.islink(file_path):
        return None
    if not os.path.isfile(file_path):
        return None
    hasher = hashlib.sha256()
    file_hash: str | None = None
    try:
        with open(file_path, "rb") as handle:
            while True:
                chunk = handle.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
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


def _calculate_directory_hash_sync(dir_path: str) -> str | None:
    dir_hash: str | None = None
    try:
        dir_hasher = hashlib.sha256()
        for root, dirs, filenames in os.walk(dir_path):
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
                file_hash = calculate_file_hash_sync(full_path)
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


async def calculate_file_hash(file_path: str) -> str | None:
    return await asyncio.to_thread(calculate_file_hash_sync, file_path)


async def calculate_directory_hash(dir_path: str) -> str | None:
    if not await asyncio.to_thread(os.path.isdir, dir_path):
        return None
    return await asyncio.to_thread(_calculate_directory_hash_sync, dir_path)
