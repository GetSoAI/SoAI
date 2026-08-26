"""SoAI - Durable domain event delivery with strict subscriber outcomes [backend/core/events/durable_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.errors.trace_logging import ensure_trace_logging
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.bus_callback_identity import describe_callback
from core.events.bus_subscriptions import (
    SubscriptionRegistry,
    SubscriptionRegistryDependencies,
)
from core.events.types_base import Event
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger

__all__ = ("DurableEventDelivery",)

LOGGER_NAME = "SoAI.core.events.durable_delivery"
OPERATION_EVENTS_DURABLE_DELIVERY_CALLBACK_FAILED = "events.durable_delivery.callback_failed"
OPERATION_EVENTS_DURABLE_DELIVERY_TIMEOUT = "events.durable_delivery.timeout"


class DurableEventDelivery:
    def __init__(
        self,
        *,
        per_callback_timeout_sec: float | None,
        default_timeout_sec: float | None,
    ) -> None:
        ensure_trace_logging()
        self._logger: TraceLogger = get_logger(LOGGER_NAME)
        self._subscriptions = SubscriptionRegistry(
            SubscriptionRegistryDependencies(logger=self._logger),
        )
        self._per_callback_timeout_sec = self._validate_timeout(
            per_callback_timeout_sec,
            label="per_callback_timeout_sec",
        )
        self._default_timeout_sec = self._validate_timeout(
            default_timeout_sec,
            label="default_timeout_sec",
        )

    @staticmethod
    def _validate_timeout(value: float | None, *, label: str) -> float | None:
        if value is None:
            return None
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise ValidationError(f"{label} must be a number or None.")
        resolved = float(value)
        if resolved <= 0.0:
            raise ValidationError(f"{label} must be a positive number or None.")
        return resolved

    def subscribe(
        self,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None:
        self._subscriptions.subscribe(
            event_type=event_type,
            callback=callback,
        )

    def unsubscribe(
        self,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None:
        self._subscriptions.unsubscribe(
            event_type=event_type,
            callback=callback,
        )

    def has_subscribers(self, event_type: type[Event]) -> bool:
        return self._subscriptions.has_subscribers(event_type)

    async def deliver(self, event: Event, *, timeout_sec: float | None = None) -> None:
        callbacks = self._subscriptions.collect_callbacks(event)
        if not callbacks:
            return
        resolved_timeout = self._default_timeout_sec if timeout_sec is None else timeout_sec
        if resolved_timeout is not None:
            if not isinstance(resolved_timeout, int | float) or isinstance(resolved_timeout, bool):
                raise ValidationError("timeout_sec must be a number or None.")
            if float(resolved_timeout) <= 0.0:
                raise ValidationError("timeout_sec must be a positive number or None.")
        if resolved_timeout is None:
            await self._deliver_callbacks(event, callbacks)
            return
        try:
            async with asyncio.timeout(float(resolved_timeout)):
                await self._deliver_callbacks(event, callbacks)
        except TimeoutError as exception:
            coerced = SoAITimeoutError(
                f"Durable delivery timed out for event {type(event).__name__}.",
                operation="events.durable_delivery.timeout",
                details={
                    "event_type": type(event).__name__,
                    "timeout_sec": float(resolved_timeout),
                },
                cause=exception,
            )
            log_exception(
                self._logger,
                coerced,
                message="Durable event delivery timed out.",
                operation=OPERATION_EVENTS_DURABLE_DELIVERY_TIMEOUT,
                details={
                    "event_type": type(event).__name__,
                    "timeout_sec": float(resolved_timeout),
                },
                level="warning",
            )
            raise coerced from exception

    async def _deliver_callbacks(
        self,
        event: Event,
        callbacks: list[Callable[[Event], Awaitable[None]]],
    ) -> None:
        per_callback_timeout_sec = self._per_callback_timeout_sec
        for callback in callbacks:
            callback_name = describe_callback(callback)
            try:
                awaitable = callback(event)
                if per_callback_timeout_sec is None:
                    await awaitable
                else:
                    await asyncio.wait_for(awaitable, timeout=per_callback_timeout_sec)
            except TimeoutError as exception:
                raise SoAITimeoutError(
                    f"Durable subscriber {callback_name} timed out for event {type(event).__name__}.",
                    operation="events.durable_delivery.callback_timeout",
                    details={
                        "event_type": type(event).__name__,
                        "subscriber": callback_name,
                        "timeout_sec": per_callback_timeout_sec,
                    },
                    cause=exception,
                ) from exception
            except asyncio.CancelledError:
                self._logger.debug(
                    "Durable event delivery cancelled for subscriber %s.",
                    callback_name,
                )
                raise
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                coerced = coerce_to_soai_error(
                    exception,
                    operation="events.durable_delivery.callback_failed",
                    details={
                        "event_type": type(event).__name__,
                        "subscriber": callback_name,
                    },
                )
                log_exception(
                    self._logger,
                    coerced,
                    message="Durable event subscriber failed.",
                    operation=OPERATION_EVENTS_DURABLE_DELIVERY_CALLBACK_FAILED,
                    details={
                        "event_type": type(event).__name__,
                        "subscriber": callback_name,
                    },
                    level="warning",
                )
                raise coerced from exception
