"""SoAI - Resumable artifact download state [backend/plugin_sdk/contracts/resumable_downloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import io
import os
import stat
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ValidationError
from core.files.staged_transfer import iter_reader_chunks
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.hardware.reserved_writes import write_reserved_bytes
from plugin_sdk.contracts.disk_claims import claim_plugin_reserved_write

if TYPE_CHECKING:
    from core.plugins.protocols_runtime import (
        PluginStorageReservationLeaseProtocol,
        PluginStorageRuntimeProtocol,
    )
    from core.types.json import JSONValue

__all__ = (
    "RetainedDownloadPrefix",
    "inspect_resumable_download",
    "open_resumable_download",
    "flush_plugin_download_buffer",
)

FILE_MODE_OWNER_READ_WRITE = 0o600


@dataclass(frozen=True, slots=True)
class RetainedDownloadPrefix:
    status: os.stat_result | None = None
    length: int = 0
    sha256: str | None = None


def inspect_resumable_download(path: str, max_bytes: int | None) -> RetainedDownloadPrefix:
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return RetainedDownloadPrefix()
    if not stat.S_ISREG(status.st_mode):
        raise ValidationError("Resumable download state is not a regular file.")
    if not status.st_size or (max_bytes is not None and status.st_size > max_bytes):
        return RetainedDownloadPrefix(status=status)
    with open_regular_binary_no_symlink(path) as handle:
        _validate_retained_status(os.fstat(handle.fileno()), status)
        digest = hashlib.sha256()
        received = 0
        for chunk in iter_reader_chunks(handle.read):
            received += len(chunk)
            if received > status.st_size:
                raise ValidationError("Resumable download state changed while hashing.")
            digest.update(chunk)
        _validate_retained_status(os.fstat(handle.fileno()), status)
        if received != status.st_size:
            raise ValidationError("Resumable download state changed while hashing.")
    return RetainedDownloadPrefix(status, received, digest.hexdigest())


def _validate_retained_status(current: os.stat_result, expected: os.stat_result) -> None:
    if (
        not stat.S_ISREG(current.st_mode)
        or current.st_dev != expected.st_dev
        or current.st_ino != expected.st_ino
        or current.st_size != expected.st_size
        or current.st_mtime_ns != expected.st_mtime_ns
    ):
        raise ValidationError("Resumable download state changed before writing.")


def open_resumable_download(
    path: str, *, append: bool, expected_status: os.stat_result | None
) -> io.BufferedWriter:
    flags = os.O_WRONLY
    if expected_status is None:
        flags |= os.O_CREAT | os.O_EXCL
    if append:
        flags |= os.O_APPEND
    if sys.platform == "win32":
        flags |= os.O_BINARY
        if os.path.islink(path):
            raise ValidationError("Resumable download state is not a regular file.")
    else:
        flags |= os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(path, flags, FILE_MODE_OWNER_READ_WRITE)
    try:
        opened_status = os.fstat(descriptor)
        if not stat.S_ISREG(opened_status.st_mode):
            raise ValidationError("Resumable download state is not a regular file.")
        if expected_status is not None:
            _validate_retained_status(opened_status, expected_status)
        if not append:
            os.ftruncate(descriptor, 0)
        handle = os.fdopen(descriptor, "ab" if append else "wb")
    except (OSError, ValueError, ValidationError):
        os.close(descriptor)
        raise
    return handle


async def flush_plugin_download_buffer(
    buffer: bytearray,
    *,
    handle: io.BufferedWriter,
    declared_reservation: PluginStorageReservationLeaseProtocol | None,
    reservation_provider: PluginStorageRuntimeProtocol,
    reservation_path: str,
    reservation_operation: str,
    reservation_details: Mapping[str, JSONValue] | None,
) -> None:
    if not buffer:
        return
    data = bytes(buffer)
    buffer.clear()
    reservation = declared_reservation
    if reservation is None:
        reservation = await reservation_provider.reserve_disk_space(
            path=reservation_path,
            required_bytes=len(data),
            operation=reservation_operation,
            details=reservation_details,
        )
    try:
        async with claim_plugin_reserved_write(
            reservation,
            size_bytes=len(data),
            cleanup_action="Plugin SDK download claim commit after write failure",
        ):
            await run_joined_thread_call(
                partial(write_reserved_bytes, handle, data, reservation=None),
                task_name="plugin-download-write",
                retain_resources_until_complete=True,
            )
    finally:
        if declared_reservation is None:
            await reservation.release()
