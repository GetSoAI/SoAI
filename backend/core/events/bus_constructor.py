"""SoAI - Event bus constructor validation and config parsing [backend/core/events/bus_constructor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.events.bus_config import parse_positive_config
from core.logging.protocols import TraceLogger
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.validation.integers import is_positive_strict_int
from core.validation.numbers import (
    coerce_float_from_json,
    coerce_int_from_json,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = (
    "EventBusConstructorValues",
    "parse_event_bus_constructor_values",
)


def _coerce_event_bus_float(value: ConfigValue) -> float | None:
    if isinstance(value, str | int | float | bool):
        return coerce_float_from_json(value, default=None)
    return None


def _coerce_event_bus_int(value: ConfigValue) -> int | None:
    if isinstance(value, str | int | float | bool):
        return coerce_int_from_json(value, default=None, parse_float_strings=False)
    return None


@dataclass(frozen=True, slots=True)
class EventBusConstructorValues:
    queue_size: int
    num_workers: int
    publish_timeout: float | None
    backpressure_warning_depth: int | None
    dispatch_timeout: float | None
    shutdown_timeout: float
    per_callback_timeout: float | None


def parse_event_bus_constructor_values(
    *,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    queue_size: int,
    num_workers: int,
    publish_timeout_sec: float | None,
    backpressure_warning_depth: int | None,
    dispatch_timeout_sec: float | None,
    shutdown_timeout_sec: float | None,
    per_callback_timeout_sec: float | None,
    logger: TraceLogger,
) -> EventBusConstructorValues:
    if cancellation_binder is None:
        raise ValidationError("EventBus requires a cancellation binder instance.")
    if finalizer_tracker is None:
        raise ValidationError("EventBus requires a finalizer tracker instance.")
    if not is_positive_strict_int(queue_size):
        raise ValidationError("EventBus queue_size must be a positive integer.")
    if not is_positive_strict_int(num_workers):
        raise ValidationError("EventBus num_workers must be a positive integer.")
    resolved_queue_size = int(queue_size)
    resolved_num_workers = int(num_workers)
    resolved_publish_timeout = parse_positive_config(
        value=publish_timeout_sec,
        coercer=_coerce_event_bus_float,
        logger=logger,
        message="Invalid EventBus publish timeout configuration",
        operation="event_bus.init",
        details={"publish_timeout_sec": publish_timeout_sec},
        default=None,
    )
    if resolved_queue_size and resolved_publish_timeout is None:
        resolved_publish_timeout = 1.0
    resolved_backpressure_warning_depth = parse_positive_config(
        value=backpressure_warning_depth,
        coercer=_coerce_event_bus_int,
        logger=logger,
        message="Invalid EventBus backpressure warning depth configuration",
        operation="event_bus.init",
        details={"backpressure_warning_depth": backpressure_warning_depth},
        default=None,
    )
    resolved_dispatch_timeout = parse_positive_config(
        value=dispatch_timeout_sec,
        coercer=_coerce_event_bus_float,
        logger=logger,
        message="Invalid EventBus dispatch timeout configuration",
        operation="event_bus.init",
        details={"dispatch_timeout_sec": dispatch_timeout_sec},
        default=None,
    )
    resolved_shutdown_timeout = parse_positive_config(
        value=shutdown_timeout_sec,
        coercer=_coerce_event_bus_float,
        logger=logger,
        message="Invalid EventBus shutdown timeout configuration",
        operation="event_bus.init",
        details={"shutdown_timeout_sec": shutdown_timeout_sec},
        default=10.0,
    )
    if resolved_shutdown_timeout is None:
        resolved_shutdown_timeout = 10.0
    resolved_per_callback_timeout = parse_positive_config(
        value=per_callback_timeout_sec,
        coercer=_coerce_event_bus_float,
        logger=logger,
        message="Invalid EventBus per-callback timeout configuration",
        operation="event_bus.init",
        details={"per_callback_timeout_sec": per_callback_timeout_sec},
        default=None,
    )
    return EventBusConstructorValues(
        queue_size=resolved_queue_size,
        num_workers=resolved_num_workers,
        publish_timeout=resolved_publish_timeout,
        backpressure_warning_depth=resolved_backpressure_warning_depth,
        dispatch_timeout=resolved_dispatch_timeout,
        shutdown_timeout=resolved_shutdown_timeout,
        per_callback_timeout=resolved_per_callback_timeout,
    )
