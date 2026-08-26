"""SoAI - Application lifecycle recovery service [backend/app/lifecycle_recovery_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.application_dependencies import ApplicationLogging
from core.di.validation import require_dependencies
from core.events.types_base import Event
from core.events.types_system import SystemRestartRequestedEvent
from core.runtime.protocols import RuntimeStateStoreProtocol

__all__ = ("LifecycleRecoveryService", "LifecycleRecoveryServiceDependencies")


@dataclass(frozen=True, slots=True)
class LifecycleRecoveryServiceDependencies:
    logging: ApplicationLogging
    runtime: RuntimeStateStoreProtocol
    request_restart: Callable[[], None]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LifecycleRecoveryServiceDependencies",
            logging=self.logging,
            request_restart=self.request_restart,
            runtime=self.runtime,
        )


class LifecycleRecoveryService:
    def __init__(self, deps: LifecycleRecoveryServiceDependencies) -> None:
        self._deps = deps

    async def handle_system_restart_requested_event(self, event: Event) -> None:
        if not isinstance(event, SystemRestartRequestedEvent):
            return
        if self._deps.runtime.is_shutting_down:
            return
        reason = event.reason
        if not reason:
            reason = "system_event"
        self._deps.logging.logger.info("System restart requested: %s", reason)
        self._deps.request_restart()
