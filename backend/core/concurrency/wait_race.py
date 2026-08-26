"""SoAI - Awaitable and event race helpers with deterministic task cleanup [backend/core/concurrency/wait_race.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from enum import Enum, auto

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import StateError
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

__all__ = (
    "WaitRaceOutcome",
    "WaitRaceResult",
    "wait_for_awaitable_or_event",
    "wait_for_first_completed_tasks",
    "wait_for_queue_or_event",
)


class WaitRaceOutcome(Enum):
    AWAITABLE_COMPLETED = auto()
    EVENT_TRIGGERED = auto()


@dataclass(frozen=True, slots=True)
class _WaitRaceToken[T]:
    outcome: WaitRaceOutcome
    value: T | None


@dataclass(frozen=True, slots=True)
class WaitRaceResult[T]:
    outcome: WaitRaceOutcome
    value: T | None


async def _settle_race_token_task[T](
    task: asyncio.Task[_WaitRaceToken[T]],
) -> _WaitRaceToken[T] | None:
    if not task.done():
        task.cancel()
    try:
        return await task
    except asyncio.CancelledError:
        return None


async def _cancel_and_gather_tasks[T](*tasks: asyncio.Task[T]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        cleanup_results = await asyncio.gather(*tasks, return_exceptions=True)
        for cleanup_result in cleanup_results:
            if isinstance(cleanup_result, asyncio.CancelledError):
                continue
            if isinstance(cleanup_result, BaseException):
                raise cleanup_result


async def wait_for_awaitable_or_event[T](
    awaitable: Coroutine[None, None, T],
    event: asyncio.Event,
) -> WaitRaceResult[T]:
    if event.is_set():
        awaitable.close()
        return WaitRaceResult(outcome=WaitRaceOutcome.EVENT_TRIGGERED, value=None)
    awaitable_task: asyncio.Task[_WaitRaceToken[T]] = create_ephemeral_task(
        _wrap_awaitable_or_event_token(
            awaitable=awaitable,
            event=None,
            outcome=WaitRaceOutcome.AWAITABLE_COMPLETED,
        ),
    )
    event_task: asyncio.Task[_WaitRaceToken[T]] = create_ephemeral_task(
        _wrap_awaitable_or_event_token(
            awaitable=None,
            event=event,
            outcome=WaitRaceOutcome.EVENT_TRIGGERED,
        ),
    )
    wait_succeeded = False
    try:
        while True:
            done, _pending = await asyncio.wait(
                {awaitable_task, event_task},
                timeout=LOCAL_IO_TIMEOUT_SEC,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if done:
                break
        wait_succeeded = True
    finally:
        if not wait_succeeded:
            await _cancel_and_gather_tasks(awaitable_task, event_task)
    if awaitable_task in done and not awaitable_task.cancelled():
        token = awaitable_task.result()
        await _cancel_and_gather_tasks(awaitable_task, event_task)
        return WaitRaceResult(outcome=token.outcome, value=token.value)
    if event_task in done:
        settled_token = await _settle_race_token_task(awaitable_task)
        await _cancel_and_gather_tasks(event_task)
        if settled_token is not None:
            return WaitRaceResult(
                outcome=settled_token.outcome,
                value=settled_token.value,
            )
        return WaitRaceResult(outcome=WaitRaceOutcome.EVENT_TRIGGERED, value=None)
    token = awaitable_task.result()
    await _cancel_and_gather_tasks(awaitable_task, event_task)
    return WaitRaceResult(outcome=token.outcome, value=token.value)


async def wait_for_queue_or_event[T](
    queue: asyncio.Queue[T],
    event: asyncio.Event,
) -> WaitRaceResult[T]:
    return await wait_for_awaitable_or_event(queue.get(), event)


async def _wrap_awaitable_or_event_token[T](
    *,
    awaitable: Coroutine[None, None, T] | None,
    event: asyncio.Event | None,
    outcome: WaitRaceOutcome,
) -> _WaitRaceToken[T]:
    if awaitable is not None:
        return _WaitRaceToken(outcome=outcome, value=await awaitable)
    if event is None:
        raise StateError("wait_race token wrapper requires either awaitable or event.")
    await event.wait()
    return _WaitRaceToken(outcome=outcome, value=None)


async def wait_for_first_completed_tasks[T](
    tasks: set[asyncio.Task[T]],
) -> set[asyncio.Task[T]]:
    if not tasks:
        return set()
    wait_succeeded = False
    try:
        while True:
            done, pending = await asyncio.wait(
                tasks,
                timeout=LOCAL_IO_TIMEOUT_SEC,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if done:
                break
        wait_succeeded = True
    finally:
        if not wait_succeeded:
            await _cancel_and_gather_tasks(*tasks)
    await _cancel_and_gather_tasks(*pending)
    return done
