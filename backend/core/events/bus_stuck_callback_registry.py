"""SoAI - Event bus stuck callback quarantine and tracking [backend/core/events/bus_stuck_callback_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, override

from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.logging.rate_limited_logger import RateLimitedLogger
from core.validation.strict_numbers import require_positive_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "EventBusCallbackCancellationRefusedError",
    "EventBusStuckCallbackRegistry",
)

EVENT_BUS_STUCK_CALLBACK_SHUTDOWN_CANCELLATION_WAIT_SEC: float = DEFAULT_CANCELLATION_TIMEOUT_SEC
_OPERATION = "event_bus.callback_cancellation_refusal"
_OPERATION_LATE_FAILURE = "event_bus.callback_quarantine.late_failure"


class EventBusCallbackCancellationRefusedError(StateError):
    def __init__(self, *, callback_id: str, event_type: str) -> None:
        super().__init__(
            "Event bus callback refused cancellation and was quarantined.",
            details={"callback": callback_id, "event_type": event_type},
            operation=_OPERATION,
        )

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (
            (),
            {
                "callback_id": (self.details or {}).get("callback"),
                "event_type": (self.details or {}).get("event_type"),
            },
        )


class EventBusStuckCallbackRegistry:
    __slots__ = (
        "_callback_pending_counts",
        "_cap",
        "_overflow_count",
        "_overflow_logger",
        "_quarantined_callbacks",
        "_tasks",
    )

    def __init__(self, *, cap: int = 64) -> None:
        self._cap = require_positive_int_strict(
            cap,
            error_message="Stuck callback tracker cap must be a positive integer.",
        )
        self._tasks: set[asyncio.Task[None]] = set()
        self._callback_pending_counts: dict[Callable[[Event], Awaitable[None]], int] = {}
        self._quarantined_callbacks: set[Callable[[Event], Awaitable[None]]] = set()
        self._overflow_count = 0
        self._overflow_logger = RateLimitedLogger(interval_seconds=10.0)

    def is_quarantined(self, callback: Callable[[Event], Awaitable[None]]) -> bool:
        return callback in self._quarantined_callbacks

    def clear_quarantine(self, callback: Callable[[Event], Awaitable[None]]) -> bool:
        if self._callback_pending_counts.get(callback, 0) > 0:
            return False
        self._quarantined_callbacks.discard(callback)
        return True

    def pending(self) -> int:
        return sum(1 for task in self._tasks if not task.done())

    def overflow_count(self) -> int:
        return self._overflow_count

    def quarantine_callback(
        self,
        *,
        task: asyncio.Task[None],
        callback_id: str,
        callback: Callable[[Event], Awaitable[None]],
        event: Event,
        trace_id: str | None,
        logger: LoggerProtocol,
    ) -> EventBusCallbackCancellationRefusedError:
        self._quarantined_callbacks.add(callback)
        error = EventBusCallbackCancellationRefusedError(
            callback_id=callback_id,
            event_type=type(event).__name__,
        )
        log_exception(
            logger,
            error,
            message="Event bus callback refused cancellation and was quarantined. Future deliveries to this subscriber will be skipped.",
            trace_id=trace_id,
            operation=_OPERATION,
            details={"callback": callback_id, "event_type": type(event).__name__},
            level="critical",
        )
        if task.done():
            return error
        should_track_task = len(self._tasks) < self._cap
        if not should_track_task:
            self._overflow_count += 1
            should_emit, suppressed = self._overflow_logger.should_emit()
            if should_emit:
                suffix = f" (suppressed={suppressed})" if suppressed else ""
                logger.critical(
                    "EventBus stuck callback tracker at cap=%d; refusing to track additional task(s). callback=%s overflow_count=%d%s",
                    self._cap,
                    callback_id,
                    self._overflow_count,
                    suffix,
                )
        self._callback_pending_counts[callback] = self._callback_pending_counts.get(callback, 0) + 1
        if should_track_task:
            self._tasks.add(task)

        def _discard(done_task: asyncio.Task[None]) -> None:
            self._tasks.discard(done_task)
            remaining = self._callback_pending_counts.get(callback, 0)
            if remaining <= 1:
                self._callback_pending_counts.pop(callback, None)
                return
            self._callback_pending_counts[callback] = remaining - 1

        def _log_late_failure(done_task: asyncio.Task[None]) -> None:
            if done_task.cancelled():
                return
            try:
                done_task.result()
            except asyncio.CancelledError:
                return
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                coerced = coerce_to_soai_error(
                    exception,
                    trace_id=trace_id,
                    operation=_OPERATION_LATE_FAILURE,
                )
                log_exception(
                    logger,
                    coerced,
                    message="Quarantined event bus callback later failed after refusing cancellation.",
                    trace_id=trace_id,
                    operation=_OPERATION_LATE_FAILURE,
                    details={"callback": callback_id, "event_type": type(event).__name__},
                    level="critical",
                )

        task.add_done_callback(_discard)
        task.add_done_callback(_log_late_failure)
        return error

    async def cancel_pending(
        self,
        *,
        logger: LoggerProtocol,
        timeout_sec: float = EVENT_BUS_STUCK_CALLBACK_SHUTDOWN_CANCELLATION_WAIT_SEC,
    ) -> None:
        pending_tasks = [task for task in self._tasks if not task.done()]
        if not pending_tasks:
            return
        logger.critical(
            "EventBus shutdown: cancelling %d quarantined stuck callback task(s) (overflow=%d).",
            len(pending_tasks),
            self._overflow_count,
        )
        still_pending = await cancel_and_await(
            pending_tasks,
            logger=logger,
            task_label="quarantined stuck callback task(s)",
            message="Cancelling quarantined stuck event bus callback task(s)...",
            timeout_sec=timeout_sec,
        )
        remaining = sum(1 for task in pending_tasks if not task.done())
        if still_pending or remaining:
            logger.critical(
                "EventBus shutdown: %d quarantined stuck callback task(s) remained pending after %.2fs.",
                remaining,
                timeout_sec,
            )
