"""SoAI - Application bootstrap preflight service [backend/app/bootstrap_preflight_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.application_dependencies import ApplicationLogging, ApplicationPaths
from app.edition_composition import EditionComposition
from app.internal_protocols import ApplicationRuntimeCoordinatorViewProtocol
from app.types_services import ApplicationServices
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.events.types_system import ConfigReloadedEvent, SystemRestartRequestedEvent
from core.timing.monotonic import monotonic_ms
from core.timing.startup_timings import StartupTimingsRecorder

__all__ = ("BootstrapPreflightService", "BootstrapPreflightServiceDependencies")


@dataclass(frozen=True, slots=True)
class BootstrapPreflightServiceDependencies:
    logging: ApplicationLogging
    paths: ApplicationPaths
    services: ApplicationServices
    runtime_coordinator: ApplicationRuntimeCoordinatorViewProtocol
    startup_timings: StartupTimingsRecorder
    edition_composition: EditionComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="BootstrapPreflightServiceDependencies",
            logging=self.logging,
            paths=self.paths,
            runtime_coordinator=self.runtime_coordinator,
            services=self.services,
            startup_timings=self.startup_timings,
            edition_composition=self.edition_composition,
        )


class BootstrapPreflightService:
    def __init__(self, deps: BootstrapPreflightServiceDependencies) -> None:
        self._deps = deps

    async def run(self, restart_event_handler: Callable[[Event], Awaitable[None]]) -> None:
        start_started_ms = monotonic_ms()
        event_bus = self._deps.runtime_coordinator.event_bus
        if event_bus is None:
            raise StateError("Event bus is not available at startup.")
        config_reload_handler = self._deps.runtime_coordinator.config_reload_handler
        reload_handler = config_reload_handler.handle_core_configuration_reload_event
        event_bus.subscribe(
            ConfigReloadedEvent,
            reload_handler,
        )
        event_bus.subscribe(SystemRestartRequestedEvent, restart_event_handler)
        ensure_host_persistence = self._deps.edition_composition.lifecycle.ensure_host_persistence
        if ensure_host_persistence is not None:
            await asyncio.to_thread(
                ensure_host_persistence,
                runtime_flags=self._deps.services.configuration.runtime_flags,
                base_dir=self._deps.paths.base_dir,
                command_executor=self._deps.services.infrastructure.command_executor,
                logger=self._deps.logging.logger,
            )
        self._deps.startup_timings.record_since_ms(
            "startup.bootstrap_core_subscriptions_ms",
            start_started_ms,
        )
