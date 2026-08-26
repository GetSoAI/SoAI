"""SoAI - Domain event outbox dispatch wait helpers [backend/app/background/domain_event_outbox_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await

__all__ = ("wait_for_outbox_dispatch_signal",)


async def wait_for_outbox_dispatch_signal(
    *,
    shutdown_event: asyncio.Event,
    dispatch_requested_event: asyncio.Event,
    interval_sec: float,
) -> bool:
    if shutdown_event.is_set():
        return False
    if dispatch_requested_event.is_set():
        dispatch_requested_event.clear()
        return True
    shutdown_waiter = create_ephemeral_task(
        shutdown_event.wait(),
        name="outbox-shutdown",
    )
    dispatch_waiter = create_ephemeral_task(
        dispatch_requested_event.wait(),
        name="outbox-dispatch-request",
    )
    try:
        done, _ = await asyncio.wait(
            {shutdown_waiter, dispatch_waiter},
            timeout=interval_sec,
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        await cancel_and_await((shutdown_waiter, dispatch_waiter), task_label="outbox wait tasks")
        for task in (shutdown_waiter, dispatch_waiter):
            if task.cancelled():
                continue
            exception = task.exception()
            if exception is not None:
                raise exception
    if shutdown_waiter in done and shutdown_event.is_set():
        return False
    if dispatch_waiter in done and dispatch_requested_event.is_set():
        dispatch_requested_event.clear()
    return True
