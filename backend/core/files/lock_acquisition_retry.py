"""SoAI - Bounded guarded file-lock acquisition with backoff [backend/core/files/lock_acquisition_retry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from filelock import Timeout

from core.errors.exceptions import SoAITimeoutError
from core.files.locking import async_guarded_file_lock, guarded_file_lock
from core.timing.constants import FILE_LOCK_RETRY_INTERVAL_SEC, MODERATE_DELAY_SEC
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.timing.sleep import sleep_seconds

__all__ = (
    "LOCK_ACQUISITION_ATTEMPTS",
    "async_retrying_guarded_file_lock",
    "retrying_guarded_file_lock",
)

LOCK_ACQUISITION_ATTEMPTS = 3
_LOCK_RETRY_JITTER_RATIO = 0.2


def _retry_delay_seconds(attempt_index: int) -> float:
    return compute_exponential_backoff_seconds(
        attempt_index,
        base_seconds=FILE_LOCK_RETRY_INTERVAL_SEC,
        maximum_seconds=MODERATE_DELAY_SEC,
        jitter_ratio=_LOCK_RETRY_JITTER_RATIO,
    )


def _acquisition_exhausted_error(
    exception: Timeout,
    *,
    timeout_seconds: float,
    operation: str,
    exhausted_message: str,
) -> SoAITimeoutError:
    return SoAITimeoutError(
        exhausted_message,
        details={
            "acquisition_attempts": LOCK_ACQUISITION_ATTEMPTS,
            "per_attempt_timeout_seconds": timeout_seconds,
        },
        operation=operation,
        cause=exception,
    )


@contextmanager
def retrying_guarded_file_lock(
    lock_path: str,
    *,
    timeout_seconds: float,
    operation: str,
    exhausted_message: str,
) -> Generator[None]:
    for attempt_index in range(LOCK_ACQUISITION_ATTEMPTS):
        entered = False
        try:
            with guarded_file_lock(lock_path, timeout=timeout_seconds):
                entered = True
                yield
                return
        except Timeout as exception:
            if entered:
                raise
            if attempt_index >= LOCK_ACQUISITION_ATTEMPTS - 1:
                raise _acquisition_exhausted_error(
                    exception,
                    timeout_seconds=timeout_seconds,
                    operation=operation,
                    exhausted_message=exhausted_message,
                ) from exception
            sleep_seconds(_retry_delay_seconds(attempt_index))


@asynccontextmanager
async def async_retrying_guarded_file_lock(
    lock_path: str,
    *,
    timeout_seconds: float,
    operation: str,
    exhausted_message: str,
) -> AsyncGenerator[None]:
    for attempt_index in range(LOCK_ACQUISITION_ATTEMPTS):
        entered = False
        try:
            async with async_guarded_file_lock(lock_path, timeout=timeout_seconds):
                entered = True
                yield
                return
        except Timeout as exception:
            if entered:
                raise
            if attempt_index >= LOCK_ACQUISITION_ATTEMPTS - 1:
                raise _acquisition_exhausted_error(
                    exception,
                    timeout_seconds=timeout_seconds,
                    operation=operation,
                    exhausted_message=exhausted_message,
                ) from exception
            await asyncio.sleep(_retry_delay_seconds(attempt_index))
