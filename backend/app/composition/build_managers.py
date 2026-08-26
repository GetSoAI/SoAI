"""SoAI - Manager composition entrypoint [backend/app/composition/build_managers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.composition.build_manager_preconditions import build_manager_preconditions
from app.composition.build_manager_services import build_manager_services
from app.internal_protocols import LifecycleCoordinatorProtocol
from app.types_services_database import DatabaseServices
from app.types_services_foundation import InfrastructureServices, TaskServices
from app.types_services_runtime import (
    ModelContextProtocolServices,
    ModelServices,
    OrchestratorServices,
    PluginServices,
    StorageServices,
)
from core.config.protocols import ConfigManagerProtocol, ConfigProtocol
from core.licensing.protocols import LicensingStatusProtocol
from core.licensing.types import Edition
from core.orchestrator.routing_config import RoutingConfig
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol, RuntimeStateStoreProtocol

if TYPE_CHECKING:
    from core.timing.startup_timings import StartupTimingsRecorder

__all__ = ("build_application_managers",)


async def build_application_managers(
    config: ConfigProtocol,
    files: FilesProtocol,
    routing_config: RoutingConfig,
    runtime_state: RuntimeStateStoreProtocol,
    database_services: DatabaseServices,
    infrastructure_services: InfrastructureServices,
    task_services: TaskServices,
    runtime_flags: RuntimeFlagsViewProtocol,
    plugin_directory: str,
    backends_directory: str,
    config_manager: ConfigManagerProtocol,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    *,
    updater_module_dependencies: ApplicationUpdaterModuleDependencies,
    lifecycle_logger: logging.Logger,
    startup_timings: StartupTimingsRecorder,
    licensing_status: LicensingStatusProtocol,
    edition: Edition,
) -> tuple[
    InfrastructureServices,
    PluginServices,
    OrchestratorServices,
    StorageServices,
    ModelContextProtocolServices,
    ModelServices,
]:
    preconditions = build_manager_preconditions(
        infrastructure_services=infrastructure_services,
        database_services=database_services,
        task_services=task_services,
    )
    return await build_manager_services(
        config=config,
        files=files,
        routing_config=routing_config,
        runtime_state=runtime_state,
        preconditions=preconditions,
        infrastructure_services=infrastructure_services,
        runtime_flags=runtime_flags,
        plugin_directory=plugin_directory,
        backends_directory=backends_directory,
        config_manager=config_manager,
        lifecycle_coordinator=lifecycle_coordinator,
        updater_module_dependencies=updater_module_dependencies,
        lifecycle_logger=lifecycle_logger,
        startup_timings=startup_timings,
        licensing_status=licensing_status,
        edition=edition,
    )
