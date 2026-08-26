"""SoAI - Async pump task lifecycle helpers [backend/core/concurrency/pump_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.logging.protocols import LoggerProtocol

__all__ = ("close_pump_task",)


async def close_pump_task(
    task: asyncio.Task[None],
    *,
    timeout_seconds: float,
    logger: LoggerProtocol,
    timeout_message: str,
) -> None:
    done, _pending = await asyncio.wait({task}, timeout=timeout_seconds)
    if done:
        if task.cancelled():
            return
        await task
        return
    logger.debug(timeout_message)
    await cancel_and_await(
        [task],
        logger=logger,
        task_label="pump task",
        timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
    )
