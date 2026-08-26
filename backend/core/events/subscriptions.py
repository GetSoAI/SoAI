"""SoAI - Event bus subscription utilities [backend/core/events/subscriptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol, EventSubscriptionProtocol
from core.events.types_base import Event
from core.events.types_system import ConfigAppliedEvent, ConfigApplyFailedEvent
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.events.types_system import ConfigReloadedEvent

__all__ = (
    "publish_config_apply_event",
    "subscribe_many",
    "unsubscribe_many",
)

OPERATION_CORE_EVENTS_SUBSCRIPTIONS_PUBLISH_CONFIG_APPLY_EVENT = (
    "core.events.subscriptions.publish_config_apply_event"
)
CONFIG_APPLY_EVENT_PUBLISH_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


async def publish_config_apply_event(
    event_bus: EventBusProtocol,
    event: ConfigReloadedEvent,
    *,
    error: str | None = None,
    logger: LoggerProtocol,
    operation: str,
    message: str,
) -> None:
    try:
        if error:
            await event_bus.publish(
                ConfigApplyFailedEvent(
                    config_name=event.config_name,
                    path=event.path,
                    content_hash=event.content_hash,
                    source=event.source,
                    error=error,
                ),
            )
        else:
            await event_bus.publish(
                ConfigAppliedEvent(
                    config_name=event.config_name,
                    path=event.path,
                    content_hash=event.content_hash,
                    source=event.source,
                ),
            )
    except CONFIG_APPLY_EVENT_PUBLISH_EXCEPTIONS as exception:
        details = {"publish_operation": operation, "config_name": event.config_name}
        if error:
            details["error"] = str(error)
        log_exception(
            logger,
            exception,
            message=message,
            operation=OPERATION_CORE_EVENTS_SUBSCRIPTIONS_PUBLISH_CONFIG_APPLY_EVENT,
            details=details,
            level="warning",
        )


def subscribe_many(
    event_bus: EventSubscriptionProtocol,
    subscriptions: Mapping[type[Event], Callable[[Event], Awaitable[None]]],
) -> None:
    if event_bus is None:
        raise ValidationError("event_bus is required.")
    if not isinstance(subscriptions, Mapping):
        raise ValidationError("subscriptions must be a mapping of event types to handlers.")
    for event_type, handler in subscriptions.items():
        if handler is None:
            continue
        event_bus.subscribe(event_type, handler)


def unsubscribe_many(
    event_bus: EventSubscriptionProtocol,
    subscriptions: Mapping[type[Event], Callable[[Event], Awaitable[None]]],
) -> None:
    if event_bus is None:
        raise ValidationError("event_bus is required.")
    if not isinstance(subscriptions, Mapping):
        raise ValidationError("subscriptions must be a mapping of event types to handlers.")
    for event_type, handler in subscriptions.items():
        if handler is None:
            continue
        event_bus.unsubscribe(event_type, handler)
