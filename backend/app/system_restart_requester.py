"""SoAI - Shared system restart-required signal emitter [backend/app/system_restart_requester.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_system import SystemRestartRequiredEvent
from core.logging.protocols import LoggerProtocol
from core.state.protocols import RestartStateManagerProtocol

__all__ = (
    "SystemRestartRequester",
    "SystemRestartRequesterDependencies",
)

OPERATION_SYSTEM_RESTART_REQUESTER_PUBLISH = "app.system_restart_requester.publish_restart_required"


@dataclass(frozen=True, slots=True)
class SystemRestartRequesterDependencies:
    restart_state_manager: RestartStateManagerProtocol
    event_bus: EventBusProtocol
    system_restart_required_event: type[SystemRestartRequiredEvent]
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SystemRestartRequesterDependencies",
            event_bus=self.event_bus,
            logger=self.logger,
            restart_state_manager=self.restart_state_manager,
            system_restart_required_event=self.system_restart_required_event,
        )


class SystemRestartRequester:
    __slots__ = ("_deps",)

    def __init__(self, deps: SystemRestartRequesterDependencies) -> None:
        self._deps = deps

    async def require_restart(self, reason: str, source: str = "unknown") -> None:
        normalized_reason = (reason or "Restart required").strip()
        normalized_source = (source or "unknown").strip()
        await self._deps.restart_state_manager.require_restart(normalized_reason, normalized_source)
        try:
            await self._deps.event_bus.publish(
                self._deps.system_restart_required_event(
                    reason=normalized_reason,
                    changed_path=normalized_source,
                ),
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logger,
                exception,
                message="Failed to publish SystemRestartRequiredEvent",
                operation=OPERATION_SYSTEM_RESTART_REQUESTER_PUBLISH,
                details={"source": normalized_source},
            )
