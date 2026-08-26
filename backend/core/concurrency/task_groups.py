"""SoAI - Core async task group utilities [backend/core/concurrency/task_groups.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from core.concurrency.queue_race import (
    QueueRaceOutcome,
    race_queue_operation_against_signals,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger

__all__ = (
    "ManagedTaskGroup",
    "QueueEventWaiter",
    "QueueWaitResult",
    "cancel_and_await",
)

LOGGER_NAME = "SoAI.core.concurrency.task_groups"
OPERATION_CORE_CONCURRENCY_TASK_GROUPS_HANDLE_TASK_COMPLETION = (
    "core.concurrency.task_groups.handle_task_completion"
)


DEFAULT_CANCELLATION_TIMEOUT_SEC: float = 0.75


@dataclass(frozen=True, slots=True)
class QueueWaitResult[T]:
    event: T | None
    retrieved_from_queue: bool


async def cancel_and_await[TaskResult](
    tasks: Iterable[asyncio.Task[TaskResult] | None],
    *,
    logger: LoggerProtocol | None = None,
    task_label: str = "tasks",
    message: str | None = None,
    log_level: int = logging.INFO,
    timeout_sec: float | None = None,
) -> int:
    task_list: list[asyncio.Task[TaskResult]] = [task for task in tasks if task]
    if not task_list:
        return 0
    pending_count = 0
    for task in task_list:
        if not task.done():
            task.cancel()
            pending_count += 1
    if pending_count and logger:
        log_message = message or f"Cancelling {pending_count} {task_label}..."
        logger.log(log_level, log_message)
    if timeout_sec is None:
        results = await asyncio.gather(*task_list, return_exceptions=True)
        for result in results:
            if isinstance(result, asyncio.CancelledError):
                continue
            if isinstance(result, BaseException) and logger is not None:
                logger.debug(
                    "Cancelled %s raised during cancellation cleanup (non-critical): %s",
                    task_label,
                    str(result),
                )
        return 0
    done, pending = await asyncio.wait(task_list, timeout=timeout_sec)

    def _consume_exception(done_task: asyncio.Task[TaskResult]) -> None:
        if done_task.cancelled():
            return
        done_task.exception()

    for completed_task in done:
        _consume_exception(completed_task)
    if not pending:
        return 0

    for pending_task in pending:
        pending_task.add_done_callback(_consume_exception)

    if logger:
        logger.warning(
            "Timed out waiting %.2fs for %s cancellation; %s task(s) still pending.",
            timeout_sec,
            task_label,
            len(pending),
        )
    return len(pending)


class QueueEventWaiter[T]:
    __slots__ = ("_queue", "_shutdown_event")

    def __init__(self, queue: asyncio.Queue[T], shutdown_event: asyncio.Event) -> None:
        self._queue = queue
        self._shutdown_event = shutdown_event

    async def wait(self, timeout: float | None = None) -> T | None:
        result = await self.wait_with_result(timeout)
        return result.event

    async def wait_with_result(self, timeout: float | None = None) -> QueueWaitResult[T]:
        if self._shutdown_event.is_set():
            await self.cancel()
            try:
                event = self._queue.get_nowait()
                return QueueWaitResult(event=event, retrieved_from_queue=True)
            except asyncio.QueueEmpty:
                return QueueWaitResult(event=None, retrieved_from_queue=False)
        if timeout is not None and timeout <= 0:
            raise SoAITimeoutError(f"Queue event wait timed out after {timeout} seconds.")
        race_result = await race_queue_operation_against_signals(
            self._queue.get(),
            (self._shutdown_event,),
            timeout_seconds=timeout,
        )
        if race_result.outcome is QueueRaceOutcome.OPERATION_COMPLETED:
            return QueueWaitResult(event=race_result.value, retrieved_from_queue=True)
        if race_result.outcome is QueueRaceOutcome.SIGNAL_FIRED:
            try:
                event = self._queue.get_nowait()
                return QueueWaitResult(event=event, retrieved_from_queue=True)
            except asyncio.QueueEmpty:
                return QueueWaitResult(event=None, retrieved_from_queue=False)
        raise SoAITimeoutError(
            f"Queue event wait timed out after {timeout if timeout is not None else 0} seconds.",
        )

    async def cancel(self) -> None:
        return


class ManagedTaskGroup:
    __slots__ = ("_label", "_logger", "_tasks")

    def __init__(
        self,
        *,
        label: str,
        logger: LoggerProtocol | None = None,
        operation_name: str | None = None,
    ) -> None:
        _ = operation_name
        self._label = label
        self._logger = logger
        self._tasks: list[asyncio.Task[None]] = []

    def _handle_task_completion(self, completed_task: asyncio.Task[None]) -> None:
        self.discard(completed_task)
        if completed_task.cancelled():
            return
        task_exception = completed_task.exception()
        if task_exception is None:
            return
        try:
            task_name = completed_task.get_name()
        except AttributeError:
            task_name = repr(completed_task)
        log_exception(
            self._logger if self._logger is not None else get_logger(LOGGER_NAME),
            task_exception,
            message=f"Background task failed: {task_name}",
            operation=OPERATION_CORE_CONCURRENCY_TASK_GROUPS_HANDLE_TASK_COMPLETION,
        )

    def track(self, task: asyncio.Task[None]) -> asyncio.Task[None]:
        if task is None:
            return task
        self._tasks.append(task)
        if task.done():
            self._handle_task_completion(task)
        else:
            task.add_done_callback(self._handle_task_completion)
        return task

    def add(self, task: asyncio.Task[None]) -> asyncio.Task[None]:
        if task is None:
            raise ValidationError("Task cannot be None.")
        self._tasks.append(task)
        return task

    def discard(self, task: asyncio.Task[None]) -> None:
        if task in self._tasks:
            self._tasks.remove(task)

    def extend(self, tasks: Iterable[asyncio.Task[None]]) -> None:
        for task in tasks:
            _ = self.add(task)

    def pending(self) -> int:
        return len([task for task in self._tasks if not task.done()])

    async def cancel(self, *, message: str | None = None) -> None:
        if not self._tasks:
            return
        await cancel_and_await(
            self._tasks,
            logger=self._logger,
            task_label=self._label,
            message=message,
        )
        self._tasks.clear()

    def __bool__(self) -> bool:
        return any(not task.done() for task in self._tasks)

    def __len__(self) -> int:
        return len(self._tasks)

    def __iter__(self) -> Iterator[asyncio.Task[None]]:
        return iter(self._tasks)
