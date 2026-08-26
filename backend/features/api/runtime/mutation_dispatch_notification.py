"""SoAI - Durable mutation dispatch notification [backend/features/api/runtime/mutation_dispatch_notification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_tasks import MutationDispatchRequestedEvent
from core.logging.trace import get_logger

__all__ = ("notify_mutation_dispatch_requested",)

LOGGER_NAME = "SoAI.features.api.mutation_dispatch_notification"
OPERATION = "api_runtime.mutation_dispatch_notification"


async def notify_mutation_dispatch_requested(event_bus: EventBusProtocol) -> None:
    try:
        await event_bus.publish(MutationDispatchRequestedEvent())
    except SoAIError as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Mutation dispatch wake-up failed; durable polling remains active.",
            operation=OPERATION,
            level="warning",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Mutation dispatch wake-up failed; durable polling remains active.",
            operation=OPERATION,
            level="warning",
        )
