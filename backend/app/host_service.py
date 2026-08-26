"""SoAI - Application host service [backend/app/host_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationLogging
from app.types_services import ApplicationServices
from core.di.validation import require_dependencies
from core.timing.monotonic import monotonic_ms
from core.timing.startup_timings import StartupTimingsRecorder

if TYPE_CHECKING:
    from app.application_host_instance import ApplicationHostInstance

__all__ = ("HostService", "HostServiceDependencies")


@dataclass(frozen=True, slots=True)
class HostServiceDependencies:
    logging: ApplicationLogging
    services: ApplicationServices
    start_unified_server: Callable[[ApplicationHostInstance], Awaitable[None]]
    start_discovery_server: Callable[[], Awaitable[None]]
    publish_runtime_endpoint: Callable[[], None]
    shutdown_server_runtime: Callable[[float], Awaitable[None]]
    stop_discovery_server_runtime: Callable[[], Awaitable[None]]
    startup_timings: StartupTimingsRecorder

    def __post_init__(self) -> None:
        require_dependencies(
            owner="HostServiceDependencies",
            logging=self.logging,
            publish_runtime_endpoint=self.publish_runtime_endpoint,
            services=self.services,
            shutdown_server_runtime=self.shutdown_server_runtime,
            start_discovery_server=self.start_discovery_server,
            start_unified_server=self.start_unified_server,
            startup_timings=self.startup_timings,
            stop_discovery_server_runtime=self.stop_discovery_server_runtime,
        )


class HostService:
    def __init__(self, deps: HostServiceDependencies) -> None:
        self._deps = deps

    async def start(self, application_instance: ApplicationHostInstance) -> None:
        server_http_enabled = self._deps.services.configuration.config.get_bool(
            "SERVER.HTTP.ENABLED",
        )
        unified_server_started_ms = monotonic_ms()
        await self._deps.start_unified_server(application_instance)
        self._deps.startup_timings.record_since_ms(
            "startup.unified_server_start_ms",
            unified_server_started_ms,
        )
        if server_http_enabled:
            discovery_started_ms = monotonic_ms()
            await self._deps.start_discovery_server()
            self._deps.startup_timings.record_since_ms(
                "startup.discovery_server_start_ms",
                discovery_started_ms,
            )
            self._deps.publish_runtime_endpoint()
            return
        self._deps.logging.logger.debug(
            "SERVER.HTTP is disabled; skipping discovery server startup.",
        )

    async def shutdown_servers(self, timeout_sec: float) -> None:
        await self._deps.shutdown_server_runtime(timeout_sec)

    async def stop_discovery_server(self) -> None:
        await self._deps.stop_discovery_server_runtime()
