"""SoAI - Async task finalization helpers [backend/core/concurrency/task_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

__all__ = ("cancel_and_await_task",)


async def cancel_and_await_task[T](task: asyncio.Task[T] | None) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return
