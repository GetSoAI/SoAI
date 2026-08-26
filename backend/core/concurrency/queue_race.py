"""SoAI - Queue operation race coordination [backend/core/concurrency/queue_race.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from enum import Enum, auto

from core.concurrency.ephemeral_tasks import create_ephemeral_task

__all__ = (
    "QueueRaceOutcome",
    "QueueRaceResult",
    "race_queue_operation_against_signals",
)


class QueueRaceOutcome(Enum):
    OPERATION_COMPLETED = auto()
    SIGNAL_FIRED = auto()
    TIMEOUT = auto()


@dataclass(frozen=True, slots=True)
class QueueRaceResult[T]:
    outcome: QueueRaceOutcome
    value: T | None
    signal_index: int | None


def _raise_if_unexpected_cleanup_exception(exception: BaseException | None) -> None:
    if exception is None:
        return
    if isinstance(exception, asyncio.CancelledError):
        return
    raise exception


async def _await_cancelled_tasks_raise_if_failed[T](
    tasks: Sequence[asyncio.Task[T]],
) -> None:
    if not tasks:
        return
    cleanup_results: list[T | BaseException] = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )
    for cleanup_result in cleanup_results:
        _raise_if_unexpected_cleanup_exception(
            cleanup_result if isinstance(cleanup_result, BaseException) else None,
        )


async def _cleanup_race_tasks[T](
    operation_task: asyncio.Task[T],
    signal_tasks: Sequence[asyncio.Task[bool]],
) -> tuple[bool, T | None]:
    recovered = False
    recovered_value: T | None = None
    cancelled_operation_tasks: list[asyncio.Task[T]] = []
    cancelled_signal_tasks: list[asyncio.Task[bool]] = []
    if operation_task.done() and not operation_task.cancelled():
        try:
            recovered_value = operation_task.result()
            recovered = True
        except asyncio.CancelledError:
            recovered_value = None
    elif not operation_task.done():
        operation_task.cancel()
        cancelled_operation_tasks.append(operation_task)
    for signal_task in signal_tasks:
        if not signal_task.done():
            signal_task.cancel()
            cancelled_signal_tasks.append(signal_task)
    await _await_cancelled_tasks_raise_if_failed(cancelled_operation_tasks)
    await _await_cancelled_tasks_raise_if_failed(cancelled_signal_tasks)
    if not recovered and operation_task.done() and not operation_task.cancelled():
        recovered_value = operation_task.result()
        recovered = True
    return (recovered, recovered_value)


async def race_queue_operation_against_signals[T](
    operation: Coroutine[None, None, T],
    signals: Sequence[asyncio.Event],
    *,
    timeout_seconds: float | None,
) -> QueueRaceResult[T]:
    operation_task = create_ephemeral_task(operation)
    signal_tasks = [create_ephemeral_task(signal.wait()) for signal in signals]
    all_tasks: set[asyncio.Task[T] | asyncio.Task[bool]] = {
        operation_task,
        *signal_tasks,
    }
    try:
        done, pending = await asyncio.wait(
            all_tasks,
            timeout=timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if operation_task in done:
            for pending_task in pending:
                pending_task.cancel()
            await _await_cancelled_tasks_raise_if_failed(signal_tasks)
            return QueueRaceResult(
                outcome=QueueRaceOutcome.OPERATION_COMPLETED,
                value=operation_task.result(),
                signal_index=None,
            )
        for signal_index, signal_task in enumerate(signal_tasks):
            if signal_task not in done:
                continue
            recovered, recovered_value = await _cleanup_race_tasks(
                operation_task,
                signal_tasks,
            )
            if recovered:
                return QueueRaceResult(
                    outcome=QueueRaceOutcome.OPERATION_COMPLETED,
                    value=recovered_value,
                    signal_index=signal_index,
                )
            return QueueRaceResult(
                outcome=QueueRaceOutcome.SIGNAL_FIRED,
                value=None,
                signal_index=signal_index,
            )
        recovered, recovered_value = await _cleanup_race_tasks(
            operation_task,
            signal_tasks,
        )
        if recovered:
            return QueueRaceResult(
                outcome=QueueRaceOutcome.OPERATION_COMPLETED,
                value=recovered_value,
                signal_index=None,
            )
        return QueueRaceResult(
            outcome=QueueRaceOutcome.TIMEOUT,
            value=None,
            signal_index=None,
        )
    except asyncio.CancelledError:
        await _cleanup_race_tasks(operation_task, signal_tasks)
        raise
