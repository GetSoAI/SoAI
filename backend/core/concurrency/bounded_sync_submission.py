"""SoAI - Deadline-bound admission of synchronous executor work [backend/core/concurrency/bounded_sync_submission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from concurrent.futures import Executor, Future
    from threading import BoundedSemaphore, RLock

    from core.concurrency.deadlines import MonotonicDeadline

__all__ = ("submit_bounded_sync_call", "bounded_sync_lock")


@contextmanager
def bounded_sync_lock(lock: RLock, deadline: MonotonicDeadline) -> Generator[None]:
    remaining = deadline.remaining_seconds()
    if remaining <= 0 or not lock.acquire(timeout=remaining):
        raise TimeoutError("Blocking lock deadline expired.")
    try:
        if deadline.expired():
            raise TimeoutError("Blocking lock deadline expired.")
        yield
    finally:
        lock.release()


def submit_bounded_sync_call[*Arguments, Result](
    executor: Executor,
    admission: BoundedSemaphore,
    deadline: MonotonicDeadline,
    operation: Callable[[*Arguments], Result],
    *arguments: *Arguments,
) -> Future[Result]:
    remaining = deadline.remaining_seconds()
    if remaining <= 0 or not admission.acquire(timeout=remaining):
        raise TimeoutError("Blocking work admission deadline expired.")
    submitted = False
    try:
        if deadline.expired():
            raise TimeoutError("Blocking work admission deadline expired.")
        future = executor.submit(operation, *arguments)
        future.add_done_callback(lambda completed: admission.release())
        submitted = True
        return future
    finally:
        if not submitted:
            admission.release()
