"""SoAI - Application lifecycle startup service [backend/app/lifecycle_startup_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.startup_steps.actors_and_services import ActorsAndServicesStartupStep
from app.startup_steps.finalization import StartupFinalizationStep
from app.startup_steps.temp_files_cleanup import TempFilesCleanupStep
from app.types_application import ApplicationContext
from core.di.validation import require_dependencies
from core.runtime.protocols import RuntimeStateStoreProtocol
from core.runtime.shutdown_marker import (
    mark_process_started,
    resolve_process_shutdown_marker_path,
)
from core.timing.monotonic import monotonic_ms
from core.timing.startup_timings import StartupTimingsRecorder
from database.core.integrity_check import verify_database_after_unclean_shutdown

__all__ = ("LifecycleStartupService", "LifecycleStartupServiceDependencies")


@dataclass(frozen=True, slots=True)
class LifecycleStartupServiceDependencies:
    runtime: RuntimeStateStoreProtocol
    startup_timings: StartupTimingsRecorder
    temp_files_cleanup: TempFilesCleanupStep
    actors_and_services: ActorsAndServicesStartupStep
    finalization: StartupFinalizationStep

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LifecycleStartupServiceDependencies",
            actors_and_services=self.actors_and_services,
            finalization=self.finalization,
            runtime=self.runtime,
            startup_timings=self.startup_timings,
            temp_files_cleanup=self.temp_files_cleanup,
        )


class LifecycleStartupService:
    def __init__(self, deps: LifecycleStartupServiceDependencies) -> None:
        self._deps = deps

    async def start_before_host(self, application_context: ApplicationContext) -> bool:
        config = application_context.services.configuration.config
        system_data_path = config.get_str("SYSTEM.PATHS.SYSTEM_DATA")
        if system_data_path:
            unclean_shutdown_detected = await mark_process_started(
                resolve_process_shutdown_marker_path(system_data_path),
                application_context.logging.lifecycle_logger,
            )
            if unclean_shutdown_detected:
                await verify_database_after_unclean_shutdown(
                    application_context.services.databases.core.reader,
                    application_context.logging.lifecycle_logger,
                )
                application_context.logging.lifecycle_logger.info(
                    "Database recovery integrity check completed successfully.",
                )
        temp_cleanup_started_ms = monotonic_ms()
        await self._deps.temp_files_cleanup.cleanup_temp_files(application_context)
        self._deps.startup_timings.record_since_ms(
            "startup.temp_files_cleanup_ms",
            temp_cleanup_started_ms,
        )
        await self._deps.actors_and_services.start_actors_and_services(application_context)
        if self._deps.runtime.shutdown_event.is_set():
            return False
        if self._deps.runtime.system_stop_event.is_set():
            return False
        sentinel_hash_started_ms = monotonic_ms()
        await application_context.api_runtime_singletons.login_password_service.timing_safe_sentinel_hash()
        self._deps.startup_timings.record_since_ms(
            "startup.login_password_sentinel_hash_ms",
            sentinel_hash_started_ms,
        )
        return True

    async def finalize_after_host(self, application_context: ApplicationContext) -> None:
        finalization_started_ms = monotonic_ms()
        await self._deps.finalization.finalize_startup(application_context)
        self._deps.startup_timings.record_since_ms(
            "startup.finalization_step_ms",
            finalization_started_ms,
        )
