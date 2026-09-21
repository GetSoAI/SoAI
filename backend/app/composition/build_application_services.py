"""SoAI - Service graph composition for application assembly [backend/app/composition/build_application_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.composition.application_bootstrap_state import ApplicationBootstrapState
from app.composition.build_managers import build_application_managers
from app.edition_composition import EditionComposition
from app.types_services_foundation import InfrastructureServices
from app.types_services_runtime import (
    HostManagementServices,
    ModelContextProtocolServices,
    ModelServices,
    OrchestratorServices,
    PluginServices,
    StorageServices,
)
from core.licensing.protocols import LicensingStatusProtocol

if TYPE_CHECKING:
    from core.timing.startup_timings import StartupTimingsRecorder

__all__ = (
    "ApplicationServiceComposition",
    "build_application_services",
)


@dataclass(frozen=True, slots=True)
class ApplicationServiceComposition:
    infrastructure_services: InfrastructureServices
    plugin_services: PluginServices
    orchestrator_services: OrchestratorServices
    storage_services: StorageServices
    model_context_protocol_services: ModelContextProtocolServices
    model_services: ModelServices
    host_management_services: HostManagementServices | None


async def build_application_services(
    *,
    bootstrap_state: ApplicationBootstrapState,
    updater_module_dependencies: ApplicationUpdaterModuleDependencies,
    lifecycle_logger: logging.Logger,
    startup_timings: StartupTimingsRecorder,
    edition_composition: EditionComposition,
    licensing_status: LicensingStatusProtocol,
) -> ApplicationServiceComposition:
    (
        infrastructure_services,
        plugin_services,
        orchestrator_services,
        storage_services,
        model_context_protocol_services,
        model_services,
    ) = await build_application_managers(
        bootstrap_state.configuration_foundation.config,
        bootstrap_state.configuration_foundation.files,
        bootstrap_state.configuration_services.routing_config,
        bootstrap_state.runtime_foundation.runtime_state,
        bootstrap_state.database_services,
        bootstrap_state.infrastructure_services,
        bootstrap_state.task_services,
        bootstrap_state.configuration_foundation.runtime_flags_service,
        bootstrap_state.paths.plugin_directory,
        bootstrap_state.paths.backends_directory,
        bootstrap_state.config_manager,
        bootstrap_state.runtime_foundation.lifecycle_coordinator,
        updater_module_dependencies=updater_module_dependencies,
        lifecycle_logger=lifecycle_logger,
        startup_timings=startup_timings,
        licensing_status=licensing_status,
        edition=edition_composition.licensing.edition,
    )
    host_management_builder = edition_composition.host_management.build_services
    host_management_services = None
    if host_management_builder is not None:
        host_management_services = host_management_builder(
            configuration_services=bootstrap_state.configuration_services,
            infrastructure_services=infrastructure_services,
            database_services=bootstrap_state.database_services,
            task_services=bootstrap_state.task_services,
            system_restart_requester=(
                bootstrap_state.runtime_foundation.runtime_state.system_restart_requester
            ),
        )
    infrastructure_services.communications.sync_actor.attach_mcp_server(
        model_context_protocol_services.coordinator.server,
    )
    infrastructure_services.communications.sync_actor.attach_licensing_status(
        licensing_status,
    )
    return ApplicationServiceComposition(
        infrastructure_services=infrastructure_services,
        plugin_services=plugin_services,
        orchestrator_services=orchestrator_services,
        storage_services=storage_services,
        model_context_protocol_services=model_context_protocol_services,
        model_services=model_services,
        host_management_services=host_management_services,
    )
