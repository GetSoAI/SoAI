"""SoAI - Bootstrap interprocess file lock [backend/core/bootstrap/lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import io
import os
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager

from core.timing.epoch import epoch_seconds
from core.timing.sleep import sleep_seconds

__all__ = ("acquire_interprocess_lock",)


def _is_lock_contended_error(exception: BaseException) -> bool:
    if isinstance(exception, BlockingIOError):
        return True
    if not isinstance(exception, OSError):
        return False
    if exception.errno in (errno.EACCES, errno.EAGAIN):
        return True
    return False


def _write_lock_metadata(handle: io.BufferedIOBase) -> None:
    pid = os.getpid()
    timestamp = int(epoch_seconds())
    payload = f"{pid}\n{timestamp}\n".encode()
    file_handle = handle
    try:
        seek_method = file_handle.seek
    except AttributeError as exception:
        raise TypeError("Lock handle must be a file object.") from exception
    try:
        write_method = file_handle.write
    except AttributeError as exception:
        raise TypeError("Lock handle must be a file object.") from exception
    try:
        flush_method = file_handle.flush
    except AttributeError as exception:
        raise TypeError("Lock handle must be a file object.") from exception
    try:
        truncate_method = file_handle.truncate
    except AttributeError as exception:
        raise TypeError("Lock handle must be a file object.") from exception
    if not (
        callable(seek_method)
        and callable(write_method)
        and callable(flush_method)
        and callable(truncate_method)
    ):
        raise TypeError("Lock handle must be a file object.")
    file_handle.seek(0)
    file_handle.write(payload)
    file_handle.truncate()
    file_handle.flush()


if sys.platform == "win32":
    import msvcrt

    _MSVCRT_LOCK_LEN = 1

    def _lock_file_region(fd: int, mode: int) -> None:
        msvcrt.locking(fd, mode, _MSVCRT_LOCK_LEN)

    def _acquire_lock(file_handle: io.BufferedIOBase) -> None:
        fd = file_handle.fileno()
        file_handle.seek(0)
        file_handle.write(b"\0")
        file_handle.flush()
        file_handle.seek(0)
        _lock_file_region(fd, msvcrt.LK_NBLCK)

    def _release_lock(file_handle: io.BufferedIOBase) -> None:
        fd = file_handle.fileno()
        file_handle.seek(0)
        _lock_file_region(fd, msvcrt.LK_UNLCK)

else:
    import fcntl

    def _acquire_lock(file_handle: io.BufferedIOBase) -> None:
        fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release_lock(file_handle: io.BufferedIOBase) -> None:
        fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def acquire_interprocess_lock(lock_path: str, *, timeout_sec: float) -> Generator[None]:
    resolved_path = os.path.abspath(lock_path)
    lock_dir = os.path.dirname(resolved_path)
    if lock_dir:
        os.makedirs(lock_dir, exist_ok=True)

    start = time.monotonic()
    sleep_delay_seconds = 0.1
    with open(resolved_path, "a+b") as handle:
        acquired = False
        while not acquired:
            try:
                _acquire_lock(handle)
                acquired = True
            except OSError as exception:
                if not _is_lock_contended_error(exception):
                    raise
                elapsed = time.monotonic() - start
                if elapsed >= timeout_sec:
                    raise TimeoutError(
                        f"Timed out waiting for interprocess lock after {timeout_sec} seconds: {resolved_path}",
                    ) from exception
                sleep_seconds(sleep_delay_seconds)
                sleep_delay_seconds = min(sleep_delay_seconds * 1.25, 1.0)

        _write_lock_metadata(handle)
        try:
            yield
        finally:
            _release_lock(handle)
