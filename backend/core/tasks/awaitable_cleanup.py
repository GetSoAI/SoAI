"""SoAI - Awaitable cleanup and callback helpers [backend/core/tasks/awaitable_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Coroutine
from functools import partial

from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "await_wrapper",
    "close_awaitable_if_cancelled",
    "create_task_with_rejection_cleanup",
    "token_is_cancelled",
    "try_close_unawaited",
)


async def await_wrapper[TaskResult](awaitable_value: Awaitable[TaskResult]) -> TaskResult:
    return await awaitable_value


def create_task_with_rejection_cleanup[TaskResult](
    awaitable_value: Awaitable[TaskResult],
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    name: str | None = None,
    rejection_cleanup: tuple[Coroutine[None, None, TaskResult], ...] = (),
) -> asyncio.Task[TaskResult]:
    wrapper = await_wrapper(awaitable_value)
    task: asyncio.Task[TaskResult] | None = None
    try:
        task = (
            asyncio.create_task(wrapper, name=name)
            if loop is None
            else loop.create_task(wrapper, name=name)
        )
        if isinstance(awaitable_value, Coroutine):
            task.add_done_callback(
                partial(close_awaitable_if_cancelled, awaitable_value=awaitable_value),
            )
        return task
    finally:
        if task is None:
            try_close_unawaited(wrapper)
            for coroutine in rejection_cleanup:
                try_close_unawaited(coroutine)


def try_close_unawaited[TaskResult](awaitable_value: Coroutine[None, None, TaskResult]) -> None:
    try:
        awaitable_value.close()
    except RuntimeError as exception:
        del exception


async def token_is_cancelled(token: CancellationTokenProtocol) -> bool:
    cancelled = token.is_cancelled()
    if isinstance(cancelled, bool):
        return cancelled
    if inspect.isawaitable(cancelled):
        return bool(await cancelled)
    return False


def close_awaitable_if_cancelled[T](
    completed_task: asyncio.Task[T],
    *,
    awaitable_value: Coroutine[None, None, T],
) -> None:
    if completed_task.cancelled():
        try_close_unawaited(awaitable_value)
