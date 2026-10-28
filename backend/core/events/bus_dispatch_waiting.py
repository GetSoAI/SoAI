"""SoAI - Event bus dispatch waiting helpers [backend/core/events/bus_dispatch_waiting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.concurrency.task_groups import DEFAULT_CANCELLATION_TIMEOUT_SEC
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.bus_callback_identity import describe_callback
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol

__all__ = (
    "await_cancelled_callback_tasks",
    "resolve_cancellation_wait_timeout",
    "wait_for_owned_callback_tasks",
    "wait_until_done",
)

_EVENT_BUS_DISPATCH_WAIT_OPERATION = "event_bus.dispatch.wait_cleanup"


def resolve_cancellation_wait_timeout(dispatch_timeout: float | None) -> float:
    if dispatch_timeout is None:
        return DEFAULT_CANCELLATION_TIMEOUT_SEC
    return max(float(dispatch_timeout), DEFAULT_CANCELLATION_TIMEOUT_SEC)


async def wait_until_done[T](task: asyncio.Task[T], timeout: float) -> bool:
    done, _pending = await asyncio.wait({task}, timeout=timeout)
    return bool(done)


async def await_cancelled_callback_tasks(
    *,
    tasks: list[asyncio.Task[Exception | None]],
    callbacks: list[Callable[[Event], Awaitable[None]]],
    event: Event,
    logger: LoggerProtocol,
    cancellation_wait_timeout: float,
) -> None:
    completed_tasks, pending_tasks = await asyncio.wait(tasks, timeout=cancellation_wait_timeout)
    trace_id = None
    for callback, completed_task in zip(callbacks, tasks, strict=True):
        if completed_task not in completed_tasks:
            continue
        try:
            completed_task.result()
        except asyncio.CancelledError:
            continue
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                trace_id=trace_id,
                operation=_EVENT_BUS_DISPATCH_WAIT_OPERATION,
            )
            log_exception(
                logger,
                coerced,
                message="Cancelled callback task raised during cancellation cleanup.",
                trace_id=trace_id,
                operation=_EVENT_BUS_DISPATCH_WAIT_OPERATION,
                details={
                    "callback": describe_callback(callback),
                    "event_type": type(event).__name__,
                },
            )
    if pending_tasks:
        pending_callbacks = [
            describe_callback(callback)
            for callback, task in zip(callbacks, tasks, strict=True)
            if task in pending_tasks
        ]
        if pending_callbacks:
            logger.warning(
                "Timed out waiting %.3fs for cancelled callback task(s) for %s. Pending callback(s): %s",
                cancellation_wait_timeout,
                type(event).__name__,
                ", ".join(pending_callbacks),
            )
            return
        logger.warning(
            "Timed out waiting %.3fs for cancelled callback task(s) for %s.",
            cancellation_wait_timeout,
            type(event).__name__,
        )


async def wait_for_owned_callback_tasks(
    *,
    tasks: list[asyncio.Task[Exception | None]],
    callbacks: list[Callable[[Event], Awaitable[None]]],
    event: Event,
    logger: LoggerProtocol,
    dispatch_timeout: float | None,
) -> set[asyncio.Task[Exception | None]]:
    try:
        _completed_tasks, pending_tasks = await asyncio.wait(tasks, timeout=dispatch_timeout)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await await_cancelled_callback_tasks(
            tasks=tasks,
            callbacks=callbacks,
            event=event,
            logger=logger,
            cancellation_wait_timeout=resolve_cancellation_wait_timeout(dispatch_timeout),
        )
        raise
    return pending_tasks
