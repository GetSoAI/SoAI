"""SoAI - Request disconnect cancellation bridge [backend/features/api/runtime/request_disconnect.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.timing.constants import ASYNC_POLL_SLICE_SEC

if TYPE_CHECKING:
    from fastapi import Request

__all__ = ("run_with_request_disconnect_watch",)


async def _watch_request_disconnect(
    request: Request,
    cancellation_event: threading.Event,
) -> None:
    while not cancellation_event.is_set():
        if await request.is_disconnected():
            cancellation_event.set()
            return
        await asyncio.sleep(ASYNC_POLL_SLICE_SEC)


async def run_with_request_disconnect_watch[ResultT](
    request: Request,
    operation: Callable[[threading.Event], Awaitable[ResultT]],
) -> ResultT:
    cancellation_event = threading.Event()

    async def run_operation() -> ResultT:
        return await operation(cancellation_event)

    watch_task = create_ephemeral_task(
        _watch_request_disconnect(request, cancellation_event),
        name="request-disconnect-watch",
        log_exceptions=False,
    )
    operation_task = create_ephemeral_task(
        run_operation(),
        name="request-disconnect-operation",
        log_exceptions=False,
    )
    try:
        while True:
            completed, _pending = await asyncio.wait(
                (operation_task, watch_task),
                timeout=ASYNC_POLL_SLICE_SEC,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if completed:
                break
        if watch_task in completed:
            await watch_task
        return await operation_task
    finally:
        cancellation_event.set()
        await uncancel_and_wait(
            cancel_and_await(
                (operation_task, watch_task),
                task_label="request disconnect operation",
                timeout_sec=None,
            ),
        )
