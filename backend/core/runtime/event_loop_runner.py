"""SoAI - Event loop runner helpers [backend/core/runtime/event_loop_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import DEFAULT_CANCELLATION_TIMEOUT_SEC, cancel_and_await
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

__all__ = ("run_coroutine_in_new_event_loop",)


def _cancel_and_drain_pending_tasks(loop: asyncio.AbstractEventLoop) -> None:
    pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
    if not pending_tasks:
        return
    pending_count = loop.run_until_complete(
        cancel_and_await(pending_tasks, timeout_sec=LOCAL_IO_TIMEOUT_SEC)
    )
    for task in pending_tasks:
        if not task.done() or task.cancelled():
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
    if pending_count:
        raise TimeoutError(
            f"Event loop shutdown timed out during tasks ({pending_count} still pending)."
        )


async def _await_shutdown_phase(awaitable: Coroutine[None, None, None], *, phase: str) -> None:
    task = create_ephemeral_task(
        awaitable, name=f"event-loop-shutdown-{phase}", log_exceptions=False
    )
    try:
        _done, pending = await asyncio.wait({task}, timeout=LOCAL_IO_TIMEOUT_SEC)
        if pending:
            raise TimeoutError(f"Event loop shutdown timed out during {phase}.")
        task.result()
    finally:
        await cancel_and_await([task], timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC)


def run_coroutine_in_new_event_loop[ResultT](awaitable: Awaitable[ResultT]) -> ResultT:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(awaitable)
    finally:
        try:
            try:
                _cancel_and_drain_pending_tasks(loop)
            finally:
                try:
                    loop.run_until_complete(
                        _await_shutdown_phase(loop.shutdown_asyncgens(), phase="async-generators")
                    )
                finally:
                    loop.run_until_complete(
                        _await_shutdown_phase(loop.shutdown_default_executor(), phase="executor")
                    )
        finally:
            asyncio.set_event_loop(None)
            loop.close()
