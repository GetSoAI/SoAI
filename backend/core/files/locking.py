"""SoAI - File locking utilities with timeout handling [backend/core/files/locking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from functools import partial

from filelock import FileLock, Timeout

from core.concurrency.deadlines import deadline_after
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.filesystem.path_coercion import normalize_filesystem_path

__all__ = (
    "async_guarded_file_lock",
    "guarded_file_lock",
)

ASYNC_LOCK_POLL_INTERVAL_SECONDS = 0.05


@contextmanager
def guarded_file_lock(
    lock_path: str,
    *,
    timeout: float,
    on_timeout: Callable[[Timeout], Exception] | Exception | None = None,
    preserve_lock_file: bool = False,
) -> Generator[None]:
    lock = FileLock(
        normalize_filesystem_path(lock_path),
        timeout=timeout,
        thread_local=False,
        preserve_lock_file=preserve_lock_file,
        fallback_to_soft=not preserve_lock_file,
    )
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
    preserve_lock_file: bool = False,
) -> AsyncGenerator[None]:
    lock = FileLock(
        normalize_filesystem_path(lock_path),
        timeout=timeout,
        thread_local=False,
        preserve_lock_file=preserve_lock_file,
        fallback_to_soft=not preserve_lock_file,
    )
    deadline = deadline_after(timeout) if timeout >= 0 else None
    acquired = False
    try:
        while not acquired:
            try:
                await run_joined_thread_call(
                    partial(lock.acquire, timeout=0),
                    task_name="core.files.locking.acquire_file_lock",
                    cancelled_result_cleanup=lambda _result: lock.release(),
                    retain_resources_until_complete=True,
                )
                acquired = True
            except Timeout as exception:
                if deadline is not None and deadline.expired():
                    if on_timeout is None:
                        raise
                    if isinstance(on_timeout, Exception):
                        raise on_timeout from exception
                    raise on_timeout(exception) from exception
                remaining = (
                    ASYNC_LOCK_POLL_INTERVAL_SECONDS
                    if deadline is None
                    else deadline.remaining_seconds()
                )
                await asyncio.sleep(min(ASYNC_LOCK_POLL_INTERVAL_SECONDS, remaining))
        yield
    finally:
        if acquired:
            await run_joined_thread_call(
                lock.release,
                task_name="core.files.locking.release_file_lock",
                retain_resources_until_complete=True,
            )
