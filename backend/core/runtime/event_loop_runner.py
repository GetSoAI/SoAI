"""SoAI - Event loop runner helpers [backend/core/runtime/event_loop_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

__all__ = ("run_coroutine_in_new_event_loop",)


def _cancel_and_drain_pending_tasks(loop: asyncio.AbstractEventLoop) -> None:
    pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
    if not pending_tasks:
        return
    for task in pending_tasks:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
    for task in pending_tasks:
        if task.cancelled():
            continue
        exception = task.exception()
        if exception is None:
            continue
        loop.call_exception_handler(
            {
                "message": "unhandled exception during event loop shutdown",
                "exception": exception,
                "task": task,
            },
        )


def run_coroutine_in_new_event_loop[ResultT](awaitable: Awaitable[ResultT]) -> ResultT:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(awaitable)
    finally:
        try:
            _cancel_and_drain_pending_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            asyncio.set_event_loop(None)
            loop.close()
