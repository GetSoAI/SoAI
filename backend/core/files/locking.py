"""SoAI - File locking utilities with timeout handling [backend/core/files/locking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager

from filelock import FileLock, Timeout

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.filesystem.path_coercion import normalize_filesystem_path

__all__ = (
    "async_guarded_file_lock",
    "guarded_file_lock",
)


@contextmanager
def guarded_file_lock(
    lock_path: str,
    *,
    timeout: float,
    on_timeout: Callable[[Timeout], Exception] | Exception | None = None,
) -> Generator[None]:
    lock = FileLock(normalize_filesystem_path(lock_path), timeout=timeout, thread_local=False)
    try:
        lock.acquire()
    except Timeout as exception:
        if on_timeout is None:
            raise
        if isinstance(on_timeout, Exception):
            raise on_timeout from exception
        raise on_timeout(exception) from exception
    try:
        yield
    finally:
        lock.release()


@asynccontextmanager
async def async_guarded_file_lock(
    lock_path: str,
    *,
    timeout: float,
    on_timeout: Callable[[Timeout], Exception] | Exception | None = None,
) -> AsyncGenerator[None]:
    lock = FileLock(normalize_filesystem_path(lock_path), timeout=timeout, thread_local=False)
    acquired = False
    try:
        try:
            await run_joined_thread_call(
                lock.acquire,
                task_name="core.files.locking.acquire_file_lock",
                cancelled_result_cleanup=lambda _result: lock.release(),
                retain_resources_until_complete=True,
            )
            acquired = True
        except Timeout as exception:
            if on_timeout is None:
                raise
            if isinstance(on_timeout, Exception):
                raise on_timeout from exception
            raise on_timeout(exception) from exception
        yield
    finally:
        if acquired:
            await run_joined_thread_call(
                lock.release,
                task_name="core.files.locking.release_file_lock",
                retain_resources_until_complete=True,
            )
