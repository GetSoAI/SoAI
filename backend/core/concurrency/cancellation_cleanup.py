"""SoAI - Bounded cancellation-safe cleanup [backend/core/concurrency/cancellation_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine

from core.concurrency.deadlines import deadline_after, wait_for_hard_deadline
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.timing.constants import BACKGROUND_TIMEOUT_SEC

__all__ = (
    "cancellation_cleanup",
    "current_task_has_pending_cancellation",
    "run_idempotent_current_task_operation",
    "shielded_cleanup",
    "uncancel_and_wait",
    "uncancel_then_cleanup",
    "wait_for_task_completion",
)


def current_task_has_pending_cancellation() -> bool:
    current_task = asyncio.current_task()
    return current_task is not None and current_task.cancelling() > 0


async def run_idempotent_current_task_operation[Result](
    operation_factory: Callable[[], Awaitable[Result]],
) -> Result:
    current_task = asyncio.current_task()
    if current_task is None:
        return await operation_factory()
    cancelled_count = 0
    try:
        while True:
            pending_cancellations = current_task.cancelling()
            for _ in range(pending_cancellations):
                current_task.uncancel()
            cancelled_count += pending_cancellations
            try:
                return await operation_factory()
            except asyncio.CancelledError:
                if current_task.cancelling() == 0:
                    raise
    finally:
        for _ in range(cancelled_count):
            current_task.cancel()


def _coerce_cleanup_future[T](cleanup: Awaitable[T], *, name: str) -> asyncio.Future[T]:
    if isinstance(cleanup, asyncio.Future):
        return cleanup

    async def _await_cleanup() -> T:
        return await cleanup

    cleanup_coroutine: Coroutine[None, None, T] = _await_cleanup()
    return create_ephemeral_task(cleanup_coroutine, name=name)


async def cancellation_cleanup[T](
    cleanup: Awaitable[T],
    *,
    timeout_seconds: float = BACKGROUND_TIMEOUT_SEC,
    propagate_cancellation: bool = False,
) -> T:
    cleanup_future = _coerce_cleanup_future(
        cleanup,
        name="core.concurrency.cancellation_cleanup.cleanup",
    )
    current_task = asyncio.current_task()
    if current_task is None:
        return await asyncio.shield(cleanup_future)
    restored_cancellation_count = 0
    deadline_monotonic: float | None = None
    restore_cancellation_requests = True

    def _complete(result: T) -> T:
        nonlocal restore_cancellation_requests, restored_cancellation_count
        restored_cancellation_count += _clear_pending_cancellations()
        if propagate_cancellation and restored_cancellation_count:
            restore_cancellation_requests = False
            raise asyncio.CancelledError()
        return result

    def _clear_pending_cancellations() -> int:
        pending_count = current_task.cancelling()
        for _ in range(pending_count):
            current_task.uncancel()
        return pending_count

    initial_pending_count = _clear_pending_cancellations()
    if initial_pending_count:
        restored_cancellation_count += initial_pending_count
        deadline_monotonic = deadline_after(timeout_seconds).deadline_monotonic
    try:
        while True:
            try:
                if deadline_monotonic is None:
                    result = await asyncio.shield(cleanup_future)
                    return _complete(result)
                result = await wait_for_hard_deadline(
                    deadline_monotonic,
                    lambda remaining: asyncio.wait_for(
                        asyncio.shield(cleanup_future),
                        timeout=remaining,
                    ),
                )
                return _complete(result)
            except TimeoutError as exception:
                if cleanup_future.done() and not cleanup_future.cancelled():
                    return _complete(cleanup_future.result())
                restore_cancellation_requests = False
                raise asyncio.CancelledError() from exception
            except asyncio.CancelledError:
                pending_count = current_task.cancelling()
                if cleanup_future.done() and not cleanup_future.cancelled():
                    return _complete(cleanup_future.result())
                if cleanup_future.cancelled() and pending_count == 0:
                    raise
                if pending_count == 0:
                    raise
                restored_cancellation_count += _clear_pending_cancellations()
                if deadline_monotonic is None:
                    deadline_monotonic = deadline_after(timeout_seconds).deadline_monotonic
    finally:
        if restore_cancellation_requests:
            for _ in range(restored_cancellation_count):
                current_task.cancel()


uncancel_and_wait = cancellation_cleanup
uncancel_then_cleanup = cancellation_cleanup


async def wait_for_task_completion[T](task: asyncio.Task[T]) -> None:
    if task.done():
        return
    completed = asyncio.Event()
    task.add_done_callback(lambda _task: completed.set())
    await cancellation_cleanup(completed.wait())


async def shielded_cleanup[T](cleanup: Awaitable[T]) -> T:
    return await asyncio.shield(cleanup)
