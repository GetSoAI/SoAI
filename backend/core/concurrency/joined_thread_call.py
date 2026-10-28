"""SoAI - Cancellation-safe joined calls on the default thread pool [backend/core/concurrency/joined_thread_call.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import admit_bounded_blocking_call
from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.concurrency.deadlines import MonotonicDeadline

__all__ = ("run_joined_thread_call",)

LOGGER_NAME = "SoAI.core.concurrency.joined_thread_call"
OPERATION_JOINED_THREAD_CLEANUP = "core.concurrency.joined_thread_call.cleanup"


async def run_joined_thread_call[*Arguments, Result, CleanupResult](
    function: Callable[[*Arguments], Result],
    *arguments: *Arguments,
    task_name: str,
    cancelled_result_cleanup: Callable[[Result], CleanupResult] | None = None,
    retain_resources_until_complete: bool = False,
    on_cancel: Callable[[], None] | None = None,
    pool: BoundedBlockingPool | None = None,
    admission_deadline: MonotonicDeadline | None = None,
) -> Result:
    thread_task: asyncio.Future[Result] = (
        asyncio.create_task(asyncio.to_thread(function, *arguments), name=task_name)
        if pool is None
        else await admit_bounded_blocking_call(
            pool, function, *arguments, deadline=admission_deadline
        )
    )
    try:
        return await asyncio.shield(thread_task)
    except asyncio.CancelledError as exception:
        if on_cancel is not None:
            try:
                on_cancel()
            except asyncio.CancelledError:
                exception.add_note("Joined thread cancellation callback was itself cancelled.")
            except HANDLED_RUNTIME_EXCEPTIONS as callback_exception:
                exception.add_note(
                    f"Joined thread cancellation callback failed: {callback_exception}"
                )
                log_exception(
                    get_logger(LOGGER_NAME),
                    callback_exception,
                    message="Joined thread cancellation callback failed.",
                    operation=OPERATION_JOINED_THREAD_CLEANUP,
                    details={"task_name": task_name},
                )
        await wait_for_task_completion(
            thread_task, retain_resources_until_complete=retain_resources_until_complete
        )
        if thread_task.cancelled():
            raise
        completion_exception = thread_task.exception()
        if completion_exception is not None:
            exception.add_note(
                f"Joined thread completion failed: {type(completion_exception).__name__}"
            )
        elif cancelled_result_cleanup is not None:
            try:
                cancelled_result_cleanup(thread_task.result())
            except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
                exception.add_note(f"Joined thread result cleanup failed: {cleanup_exception}")
                log_exception(
                    get_logger(LOGGER_NAME),
                    cleanup_exception,
                    message="Joined thread result cleanup failed after cancellation.",
                    operation=OPERATION_JOINED_THREAD_CLEANUP,
                    details={"task_name": task_name},
                )
        raise
