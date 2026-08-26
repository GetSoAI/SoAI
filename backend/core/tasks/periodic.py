"""SoAI - Core periodic task utilities [backend/core/tasks/periodic.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = (
    "run_periodic_task",
    "wait_for_periodic_tick",
)

OPERATION = "core_tasks.run_periodic_task"


async def wait_for_periodic_tick(
    *,
    stop_event: asyncio.Event,
    interval_seconds: float,
    wake_event: asyncio.Event | None = None,
) -> bool:
    effective_interval = interval_seconds if interval_seconds and interval_seconds > 0 else 0.1
    if stop_event.is_set():
        return False
    if wake_event is not None and wake_event.is_set():
        wake_event.clear()
        return True
    if wake_event is None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=effective_interval)
        except TimeoutError:
            return True
        return False
    stop_waiter = create_ephemeral_task(stop_event.wait(), name="periodic-stop")
    wake_waiter = create_ephemeral_task(wake_event.wait(), name="periodic-wake")
    try:
        done, _ = await asyncio.wait(
            {stop_waiter, wake_waiter},
            timeout=effective_interval,
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        await cancel_and_await((stop_waiter, wake_waiter))
    if stop_waiter in done and stop_event.is_set():
        return False
    if wake_waiter in done and wake_event.is_set():
        wake_event.clear()
    return True


async def run_periodic_task(
    stop_event: asyncio.Event,
    interval_seconds: float,
    task: Callable[[], Awaitable[None]],
    *,
    logger: LoggerProtocol | None = None,
    task_name: str | None = None,
    run_immediately: bool = False,
) -> None:
    name = task_name
    if not name:
        try:
            name_value = task.__name__
        except AttributeError:
            name_value = None
        name = name_value or "periodic_task"
    effective_interval = interval_seconds if interval_seconds and interval_seconds > 0 else 0.1
    try:
        if run_immediately:
            await task()
    except RECOVERABLE_EXCEPTIONS as exception:
        if logger:
            log_exception(
                logger,
                exception,
                message=f"Error in periodic task '{name}' during initial execution",
                operation=OPERATION,
            )
    while not stop_event.is_set():
        try:
            should_run = await wait_for_periodic_tick(
                stop_event=stop_event,
                interval_seconds=effective_interval,
            )
        except asyncio.CancelledError:
            break
        if not should_run:
            break
        try:
            await task()
        except RECOVERABLE_EXCEPTIONS as exception:
            if logger:
                log_exception(
                    logger,
                    exception,
                    message=f"Error in periodic task '{name}'",
                    operation=OPERATION,
                )
    if logger:
        logger.debug("Periodic task '%s' has shut down.", name)
