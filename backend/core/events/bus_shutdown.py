"""SoAI - Event bus worker shutdown helpers [backend/core/events/bus_shutdown.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.logging.protocols import TraceLogger

__all__ = ("shutdown_worker_tasks",)


async def shutdown_worker_tasks[T](
    *,
    queues: list[asyncio.Queue[T]],
    worker_tasks: list[asyncio.Task[None]],
    sentinel: T,
    shutdown_timeout: float,
    logger: TraceLogger,
) -> None:
    if not worker_tasks:
        return
    for queue in queues:
        try:
            queue.put_nowait(sentinel)
        except asyncio.QueueFull:
            logger.warning("Event bus queue full during shutdown, cancelling workers directly.")
            for task in worker_tasks:
                task.cancel()
            break
    try:
        await asyncio.wait_for(
            asyncio.gather(*worker_tasks, return_exceptions=True),
            timeout=shutdown_timeout,
        )
    except TimeoutError:
        logger.warning(
            "Event bus workers did not shut down within %.3fs, cancelling.",
            shutdown_timeout,
        )
        for task in worker_tasks:
            if not task.done():
                task.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*worker_tasks, return_exceptions=True),
                timeout=shutdown_timeout,
            )
        except TimeoutError:
            logger.critical(
                "Event bus workers remained pending after forced cancellation timeout (%.3fs). Continuing shutdown with %s pending worker(s).",
                shutdown_timeout,
                sum(1 for task in worker_tasks if not task.done()),
            )
    worker_tasks.clear()
