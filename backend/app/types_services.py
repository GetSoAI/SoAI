"""SoAI - Aggregate application service container type [backend/app/types_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.types_services_database import DatabaseServices
from app.types_services_foundation import (
    ConfigurationServices,
    InfrastructureServices,
    TaskServices,
)
from app.types_services_licensing import LicensingServices
from app.types_services_runtime import (
    HostManagementServices,
    LifecycleServices,
    ModelContextProtocolServices,
    ModelServices,
    OrchestratorServices,
    PluginServices,
    StorageServices,
)
from core.di.validation import require_dependencies

__all__ = ("ApplicationServices",)


@dataclass(slots=True, frozen=True)
class ApplicationServices:
    configuration: ConfigurationServices
    infrastructure: InfrastructureServices
    licensing: LicensingServices
    databases: DatabaseServices
    tasks: TaskServices
    orchestrator: OrchestratorServices
    plugins: PluginServices
    storage: StorageServices
    model_context_protocol: ModelContextProtocolServices
    lifecycle: LifecycleServices
    models: ModelServices
    host_management: HostManagementServices | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationServices",
            configuration=self.configuration,
            infrastructure=self.infrastructure,
            licensing=self.licensing,
            databases=self.databases,
            tasks=self.tasks,
            orchestrator=self.orchestrator,
            plugins=self.plugins,
            storage=self.storage,
            model_context_protocol=self.model_context_protocol,
            lifecycle=self.lifecycle,
            models=self.models,
        )
