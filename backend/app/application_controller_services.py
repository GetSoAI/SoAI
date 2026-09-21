"""SoAI - Application controller service composition [backend/app/application_controller_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.application_dependencies import (
    ApplicationLogging,
    ApplicationModuleDependencies,
    ApplicationPaths,
)
from app.application_update_service import (
    ApplicationUpdateService,
    ApplicationUpdateServiceDependencies,
)
from app.bootstrap_preflight_service import (
    BootstrapPreflightService,
    BootstrapPreflightServiceDependencies,
)
from app.edition_composition import EditionComposition
from app.host_service import HostService, HostServiceDependencies
from app.internal_protocols import ApplicationRuntimeCoordinatorViewProtocol
from app.lifecycle.budgets import LifecycleShutdownBudgets
from app.lifecycle_recovery_service import (
    LifecycleRecoveryService,
    LifecycleRecoveryServiceDependencies,
)
from app.lifecycle_shutdown_service import (
    LifecycleShutdownService,
    LifecycleShutdownServiceDependencies,
)
from app.lifecycle_startup_service import (
    LifecycleStartupService,
    LifecycleStartupServiceDependencies,
)
from app.server import (
    ApplicationServerCoordinator,
    ApplicationServerCoordinatorDependencies,
)
from app.shutdown import (
    ApplicationShutdownCoordinator,
    ApplicationShutdownCoordinatorDependencies,
)
from app.startup_steps.actors_and_services import ActorsAndServicesStartupStep
from app.startup_steps.dependencies import StartupStepDependencies
from app.startup_steps.finalization import StartupFinalizationStep
from app.startup_steps.temp_files_cleanup import TempFilesCleanupStep
from app.types_application import ApplicationContext
from app.types_services import ApplicationServices
from core.di.validation import require_dependencies
from core.runtime.protocols import RuntimeStateStoreProtocol
from core.timing.startup_timings import StartupTimingsRecorder

__all__ = (
    "ApplicationControllerServices",
    "ApplicationControllerServicesDependencies",
    "build_application_controller_services",
)


@dataclass(frozen=True, slots=True)
class ApplicationControllerServices:
    preflight: BootstrapPreflightService
    startup: LifecycleStartupService
    host: HostService
    shutdown: LifecycleShutdownService
    recovery: LifecycleRecoveryService
    update: ApplicationUpdateService


@dataclass(frozen=True, slots=True)
class ApplicationControllerServicesDependencies:
    logging: ApplicationLogging
    paths: ApplicationPaths
    runtime: RuntimeStateStoreProtocol
    services: ApplicationServices
    module_dependencies: ApplicationModuleDependencies
    runtime_coordinator: ApplicationRuntimeCoordinatorViewProtocol
    startup_timings: StartupTimingsRecorder
    request_restart: Callable[[], None]
    edition_composition: EditionComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationControllerServicesDependencies",
            logging=self.logging,
            module_dependencies=self.module_dependencies,
            paths=self.paths,
            request_restart=self.request_restart,
            runtime=self.runtime,
            runtime_coordinator=self.runtime_coordinator,
            services=self.services,
            startup_timings=self.startup_timings,
            edition_composition=self.edition_composition,
        )


def build_application_controller_services(
    deps: ApplicationControllerServicesDependencies,
) -> ApplicationControllerServices:
    server_coordinator = ApplicationServerCoordinator(
        ApplicationServerCoordinatorDependencies(
            logging=deps.logging,
            runtime_state=deps.runtime,
            base_dir=deps.paths.base_dir,
            pid_file_path=deps.paths.pid_file_path,
            configuration=deps.services.configuration.config,
            runtime_flags=deps.services.configuration.runtime_flags,
            files=deps.services.configuration.files,
            database_users=deps.services.databases.users,
            database_plugins=deps.services.databases.plugins,
            database_licensing=deps.services.databases.licensing,
            logging_manager=deps.services.infrastructure.log_manager,
            lifecycle_coordinator=deps.services.lifecycle.coordinator,
            discovery_service=deps.services.lifecycle.discovery_service,
            hardware_manager=deps.services.infrastructure.hardware.manager,
            cancellation_binder=deps.services.tasks.cancellation.binder,
            finalizer_tracker=deps.services.tasks.cancellation.finalizer_tracker,
            module_dependencies=deps.module_dependencies.server,
            edition=deps.edition_composition.capabilities.edition,
        ),
    )
    startup_dependencies = StartupStepDependencies(
        runtime_coordinator=deps.runtime_coordinator,
        module_dependencies=deps.module_dependencies.startup,
        startup_timings=deps.startup_timings,
    )
    host_service = HostService(
        HostServiceDependencies(
            logging=deps.logging,
            services=deps.services,
            start_unified_server=server_coordinator.start_unified_server,
            start_discovery_server=server_coordinator.start_discovery_server,
            publish_runtime_endpoint=server_coordinator.publish_runtime_endpoint,
            shutdown_server_runtime=server_coordinator.shutdown_servers,
            stop_discovery_server_runtime=server_coordinator.stop_discovery_server,
            startup_timings=deps.startup_timings,
        ),
    )
    shutdown_coordinator = ApplicationShutdownCoordinator(
        ApplicationShutdownCoordinatorDependencies(),
    )

    async def run_shutdown_sequence(
        application_context: ApplicationContext,
        budgets: LifecycleShutdownBudgets,
    ) -> None:
        await shutdown_coordinator.run_shutdown_sequence(
            application_context=application_context,
            budgets=budgets,
        )

    return ApplicationControllerServices(
        preflight=BootstrapPreflightService(
            BootstrapPreflightServiceDependencies(
                logging=deps.logging,
                paths=deps.paths,
                services=deps.services,
                runtime_coordinator=deps.runtime_coordinator,
                startup_timings=deps.startup_timings,
                edition_composition=deps.edition_composition,
            ),
        ),
        startup=LifecycleStartupService(
            LifecycleStartupServiceDependencies(
                runtime=deps.runtime,
                startup_timings=deps.startup_timings,
                temp_files_cleanup=TempFilesCleanupStep(startup_dependencies),
                actors_and_services=ActorsAndServicesStartupStep(startup_dependencies),
                finalization=StartupFinalizationStep(startup_dependencies),
            ),
        ),
        host=host_service,
        shutdown=LifecycleShutdownService(
            LifecycleShutdownServiceDependencies(
                logging=deps.logging,
                runtime=deps.runtime,
                services=deps.services,
                runtime_coordinator=deps.runtime_coordinator,
                host_service=host_service,
                run_shutdown_sequence=run_shutdown_sequence,
            ),
        ),
        recovery=LifecycleRecoveryService(
            LifecycleRecoveryServiceDependencies(
                logging=deps.logging,
                runtime=deps.runtime,
                request_restart=deps.request_restart,
            ),
        ),
        update=ApplicationUpdateService(
            ApplicationUpdateServiceDependencies(
                logging=deps.logging,
                paths=deps.paths,
                runtime=deps.runtime,
                services=deps.services,
                runtime_coordinator=deps.runtime_coordinator,
                updater=deps.edition_composition.updater,
            ),
        ),
    )
