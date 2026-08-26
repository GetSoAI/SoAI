"""SoAI - File locking utilities with timeout handling [backend/core/files/locking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager

from filelock import FileLock, Timeout

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger

__all__ = (
    "async_guarded_file_lock",
    "guarded_file_lock",
)

LOGGER_NAME = "SoAI.core.files.locking"
OPERATION = "core.files.locking.async_guarded_file_lock"


@contextmanager
def guarded_file_lock(
    lock_path: str,
    *,
    timeout: float,
    on_timeout: Callable[[Timeout], Exception] | Exception | None = None,
) -> Generator[None]:
    lock = FileLock(lock_path, timeout=timeout, thread_local=False)
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
    lock = FileLock(lock_path, timeout=timeout, thread_local=False)
    acquired = False
    acquire_task = asyncio.create_task(
        asyncio.to_thread(lock.acquire),
        name="core.files.locking.acquire_file_lock",
    )
    try:
        try:
            await asyncio.shield(acquire_task)
            acquired = True
        except Timeout as exception:
            if on_timeout is None:
                raise
            if isinstance(on_timeout, Exception):
                raise on_timeout from exception
            raise on_timeout(exception) from exception
        except asyncio.CancelledError:
            try:
                await uncancel_and_wait(acquire_task)
                acquired = True
            except Timeout:
                acquired = False
            except (OSError, RuntimeError, asyncio.CancelledError) as exception:
                logger = get_logger(LOGGER_NAME)
                coerced = coerce_to_soai_error(
                    exception,
                    operation="core.files.locking.async_guarded_file_lock",
                )
                log_exception(
                    logger,
                    coerced,
                    message="Exception during file lock acquisition cleanup after cancellation",
                    operation=OPERATION,
                )
                acquired = False
            raise
        yield
    finally:
        if acquired:
            await uncancel_and_wait(asyncio.to_thread(lock.release))
