"""SoAI - Event bus dispatch logging helpers [backend/core/events/bus_dispatch_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.events.bus_callback_identity import describe_callback
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol

__all__ = (
    "log_dispatch_callback_exception",
    "resolve_event_trace_id",
)

EVENT_BUS_DISPATCH_CALLBACK_OPERATION = "event_bus.dispatch.callback"


def resolve_event_trace_id(event: Event | None) -> str | None:
    if event is None:
        return None
    trace_id = event.trace_id
    return trace_id if trace_id else None


def log_dispatch_callback_exception(
    *,
    logger: LoggerProtocol,
    exception: BaseException,
    callback: Callable[[Event], Awaitable[None]],
    event: Event,
    message: str,
    trace_id: str | None,
) -> None:
    callback_identity = describe_callback(callback)
    coerced = coerce_to_soai_error(
        exception,
        trace_id=trace_id,
        operation=EVENT_BUS_DISPATCH_CALLBACK_OPERATION,
    )
    log_exception(
        logger,
        coerced,
        message=message,
        trace_id=trace_id,
        operation=EVENT_BUS_DISPATCH_CALLBACK_OPERATION,
        details={
            "callback": callback_identity,
            "event_type": type(event).__name__,
        },
    )
