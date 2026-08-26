"""SoAI - Orchestrator shutdown task cancellation [backend/orchestrator/control/shutdown_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.task_groups import cancel_and_await
from core.logging.protocols import TraceLogger

__all__ = ("cancel_shutdown_tasks",)


async def cancel_shutdown_tasks(
    *,
    logger: TraceLogger,
    background_tasks: list[asyncio.Task[None]],
    active_inference_tasks: list[asyncio.Task[bool]],
    timeout_seconds: float,
) -> None:
    pending_background = sum(not task.done() for task in background_tasks if task is not None)
    pending_inference = sum(not task.done() for task in active_inference_tasks if task is not None)
    pending_total = pending_background + pending_inference
    log_message = (
        f"Cancelling {pending_total} background and in-flight inference tasks..."
        if pending_total
        else None
    )
    await cancel_and_await(
        tasks=[task for task in background_tasks if task is not None],
        logger=logger if pending_total else None,
        task_label="background tasks",
        message=log_message,
        timeout_sec=timeout_seconds,
    )
    await cancel_and_await(
        tasks=[task for task in active_inference_tasks if task is not None],
        logger=logger if pending_total else None,
        task_label="in-flight inference tasks",
        message=None,
        timeout_sec=timeout_seconds,
    )
