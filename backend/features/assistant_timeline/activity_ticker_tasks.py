"""SoAI - Shared assistant activity ticker task helpers [backend/features/assistant_timeline/activity_ticker_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

__all__ = ("take_activity_ticker_exception",)


def take_activity_ticker_exception(
    activity_tick_task: asyncio.Task[None] | None,
) -> tuple[asyncio.Task[None] | None, BaseException | None]:
    if activity_tick_task is None:
        return None, None
    if not activity_tick_task.done():
        return activity_tick_task, None
    try:
        task_exception = activity_tick_task.exception()
    except asyncio.CancelledError:
        task_exception = None
    return None, task_exception
