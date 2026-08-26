"""SoAI - Domain event outbox dispatch notification [backend/database/repositories/users/domain_event_outbox_dispatch_signal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_system import DomainEventOutboxDispatchRequestedEvent
from core.logging.trace import get_logger

__all__ = ("notify_domain_event_outbox_dispatch_requested",)

LOGGER_NAME = "SoAI.database.repositories.domain_event_outbox_dispatch_signal"
OPERATION = "database.users.domain_event_outbox_dispatch_signal"


def notify_domain_event_outbox_dispatch_requested(event_bus: EventBusProtocol | None) -> None:
    if event_bus is None:
        return
    try:
        try_publish_nowait = event_bus.try_publish_nowait
    except AttributeError:
        return
    if not callable(try_publish_nowait):
        return
    try:
        try_publish_nowait(DomainEventOutboxDispatchRequestedEvent())
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Durable user event committed but outbox wake signal failed.",
            operation=OPERATION,
            level="warning",
        )
