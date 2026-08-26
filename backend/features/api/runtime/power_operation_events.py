"""SoAI - Durable power operation event publication [backend/features/api/runtime/power_operation_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_system import PowerOperationChangedEvent
from core.logging.protocols import TraceLogger
from core.system.power_operation_projection import project_power_operation_public_fields
from core.system.power_operations import PowerOperation

__all__ = (
    "PowerOperationEventPublisher",
    "PowerOperationEventPublisherDependencies",
)

_OPERATION = "api_power.lifecycle_publication"


@dataclass(frozen=True, slots=True)
class PowerOperationEventPublisherDependencies:
    event_bus: EventBusProtocol
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PowerOperationEventPublisherDependencies",
            event_bus=self.event_bus,
            logger=self.logger,
        )


class PowerOperationEventPublisher:
    def __init__(self, deps: PowerOperationEventPublisherDependencies) -> None:
        self._event_bus = deps.event_bus
        self._logger = deps.logger

    async def publish(self, operation: PowerOperation) -> None:
        try:
            await self._event_bus.publish(
                PowerOperationChangedEvent(**project_power_operation_public_fields(operation))
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Power operation lifecycle publication failed.",
                operation=_OPERATION,
                level="warning",
            )
