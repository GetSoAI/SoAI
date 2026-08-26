"""SoAI - Task registry completion waiting operations [backend/tasks/registry/completion_waiting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAITimeoutError

if TYPE_CHECKING:
    from core.tasks.task import Task

__all__ = ("wait_for_task_completion",)


async def wait_for_task_completion(
    task_id: str,
    *,
    timeout: float | None = None,
    get_task_fn: Callable[[str], Coroutine[None, None, Task | None]],
    ensure_completion_event_fn: Callable[[str, bool], Coroutine[None, None, asyncio.Event]],
    release_completion_event_fn: Callable[[str], Coroutine[None, None, None]],
) -> Task | None:
    task = await get_task_fn(task_id)
    if task is None:
        return None
    if task.status.is_terminal():
        return task
    event = await ensure_completion_event_fn(task_id, False)
    refreshed = await get_task_fn(task_id)
    if refreshed is not None and refreshed.status.is_terminal():
        await ensure_completion_event_fn(task_id, True)
        return refreshed
    effective_timeout: float | None
    if timeout is None or timeout <= 0:
        effective_timeout = None
    else:
        effective_timeout = float(timeout)
    try:
        if effective_timeout is None:
            await event.wait()
        else:
            await asyncio.wait_for(event.wait(), timeout=effective_timeout)
    except TimeoutError as exception:
        raise SoAITimeoutError(
            f"Task '{task_id}' did not reach a terminal state within {effective_timeout} seconds.",
        ) from exception
    finally:
        if not event.is_set():
            await release_completion_event_fn(task_id)
    return await get_task_fn(task_id)
