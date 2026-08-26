"""SoAI - Shutdown-aware wait helpers [backend/core/concurrency/shutdown_waits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)

__all__ = ("wait_for_shutdown_or_schedule_change",)


async def wait_for_shutdown_or_schedule_change(
    shutdown_event: asyncio.Event,
    schedule_changed_event: asyncio.Event | None,
    timeout_sec: float,
) -> str:
    if shutdown_event.is_set():
        return "shutdown"
    if timeout_sec <= 0:
        return "timeout"
    if schedule_changed_event is None:
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=timeout_sec)
            return "shutdown"
        except TimeoutError:
            return "timeout"
    shutdown_task = create_ephemeral_task(shutdown_event.wait())
    schedule_task = create_ephemeral_task(schedule_changed_event.wait())
    try:
        done, _ = await asyncio.wait(
            {shutdown_task, schedule_task},
            timeout=timeout_sec,
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        await cancel_and_await(
            [shutdown_task, schedule_task],
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        )
    if shutdown_task in done:
        return "shutdown"
    if schedule_task in done:
        schedule_changed_event.clear()
        return "schedule_changed"
    return "timeout"
