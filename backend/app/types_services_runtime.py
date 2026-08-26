"""SoAI - Runtime/domain service container dataclasses [backend/app/types_services_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.internal_protocols import DiscoveryServerProtocol, LifecycleCoordinatorProtocol
from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from app.backup.backup_service import ApplicationBackupService
    from app.media_parsing_services import MediaParsingServices
    from core.files.protocols import (
        DocumentReaderProtocol,
        FileExplorerBatchProtocol,
        FileExplorerCoreProtocol,
        FileExplorerDownloadProtocol,
        FileExplorerListingProtocol,
        FileExplorerSearchProtocol,
        FileExplorerTaskLauncherProtocol,
        FileParserRegistryFactoryProtocol,
    )
    from core.mcp.protocols_main import MCPServicesCoordinatorProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelManagerProtocol,
        ModelParameterServiceProtocol,
        ModelProviderCoordinatorProtocol,
        ModelResolutionServiceProtocol,
        VirtualModelServiceProtocol,
    )
    from core.orchestrator.protocols_lifecycle import (
        OrchestratorControlProtocol,
        OrchestratorLifecycleProtocol,
    )
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from core.orchestrator.protocols_scheduler import OrchestratorSchedulerProtocol
    from core.os.protocols import (
        OSDriversStatusServiceProtocol,
        OSDriversTaskServiceProtocol,
        OSMaintenanceLogsServiceProtocol,
        OSMaintenancePowerServiceProtocol,
        OSMaintenanceSshSafeDisableServiceProtocol,
        OSMaintenanceSshServiceProtocol,
        OSMaintenanceStatusServiceProtocol,
        OSMaintenanceSystemdServiceProtocol,
        OSMaintenanceTimeSyncServiceProtocol,
        OSManagerProtocol,
        OSNetworkSafeApplyServiceProtocol,
        OSNetworkStatusServiceProtocol,
        OSStorageMutationServiceProtocol,
        OSStorageStatusServiceProtocol,
        OSUpdatesStatusServiceProtocol,
        OSUpdatesTaskServiceProtocol,
        OSUserSyncServiceProtocol,
    )
    from core.plugins.protocols import PluginManagerProtocol
    from core.tool_calls.protocols import ToolCallProcessingProtocol
    from core.webui_manager.protocols import WebUIManagerProtocol
    from files.manager import FileManager
    from orchestrator.director import InactivityMonitor
    from orchestrator.execution.active_inference_service import ActiveInferenceService
    from orchestrator.execution.inference_executor import OrchestratorInferenceExecutor
    from orchestrator.execution.outcomes import OutcomeManager
    from orchestrator.handlers import OrchestratorHandlers

__all__ = (
    "LifecycleServices",
    "ModelContextProtocolServices",
    "ModelServices",
    "HostManagementServices",
    "OrchestratorServices",
    "PluginServices",
    "StorageServices",
)


@dataclass(slots=True, frozen=True)
class OrchestratorServices:
    queue: OrchestratorQueueProtocol
    scheduler: OrchestratorSchedulerProtocol
    inference_executor: OrchestratorInferenceExecutor
    outcomes: OutcomeManager
    active_inferences: ActiveInferenceService
    handlers: OrchestratorHandlers
    lifecycle: OrchestratorLifecycleProtocol
    control: OrchestratorControlProtocol
    tool_call_processor: ToolCallProcessingProtocol
    inactivity_monitor: InactivityMonitor

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorServices",
            queue=self.queue,
            scheduler=self.scheduler,
            inference_executor=self.inference_executor,
            outcomes=self.outcomes,
            active_inferences=self.active_inferences,
            handlers=self.handlers,
            lifecycle=self.lifecycle,
            control=self.control,
            tool_call_processor=self.tool_call_processor,
            inactivity_monitor=self.inactivity_monitor,
        )


@dataclass(slots=True, frozen=True)
class PluginServices:
    plugin_manager: PluginManagerProtocol
    webui_manager: WebUIManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginServices",
            plugin_manager=self.plugin_manager,
            webui_manager=self.webui_manager,
        )


@dataclass(slots=True, frozen=True)
class StorageServices:
    file_manager: FileManager
    backup_service: ApplicationBackupService
    document_reader: DocumentReaderProtocol
    parser_registry_factory: FileParserRegistryFactoryProtocol
    media_parsing: MediaParsingServices
    file_explorer_core: FileExplorerCoreProtocol | None
    file_explorer_batch: FileExplorerBatchProtocol | None
    file_explorer_tasks: FileExplorerTaskLauncherProtocol | None
    file_explorer_search: FileExplorerSearchProtocol | None
    file_explorer_download: FileExplorerDownloadProtocol | None
    file_explorer_listings: FileExplorerListingProtocol | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="StorageServices",
            file_manager=self.file_manager,
            backup_service=self.backup_service,
            document_reader=self.document_reader,
            parser_registry_factory=self.parser_registry_factory,
            media_parsing=self.media_parsing,
        )


@dataclass(slots=True, frozen=True)
class ModelContextProtocolServices:
    coordinator: MCPServicesCoordinatorProtocol

    def __post_init__(self) -> None:
        require_dependencies(owner="ModelContextProtocolServices", coordinator=self.coordinator)


@dataclass(slots=True, frozen=True)
class LifecycleServices:
    coordinator: LifecycleCoordinatorProtocol
    discovery_service: DiscoveryServerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LifecycleServices",
            coordinator=self.coordinator,
            discovery_service=self.discovery_service,
        )


@dataclass(slots=True, frozen=True)
class HostManagementServices:
    manager: OSManagerProtocol
    drivers_status: OSDriversStatusServiceProtocol
    drivers_tasks: OSDriversTaskServiceProtocol
    network_status: OSNetworkStatusServiceProtocol
    network_safe_apply: OSNetworkSafeApplyServiceProtocol
    storage_status: OSStorageStatusServiceProtocol
    storage_mutation: OSStorageMutationServiceProtocol
    users: OSUserSyncServiceProtocol
    updates_status: OSUpdatesStatusServiceProtocol
    updates_tasks: OSUpdatesTaskServiceProtocol
    maintenance_status: OSMaintenanceStatusServiceProtocol
    maintenance_systemd: OSMaintenanceSystemdServiceProtocol
    maintenance_logs: OSMaintenanceLogsServiceProtocol
    maintenance_time_sync: OSMaintenanceTimeSyncServiceProtocol
    maintenance_power: OSMaintenancePowerServiceProtocol
    ssh: OSMaintenanceSshServiceProtocol
    ssh_safe_disable: OSMaintenanceSshSafeDisableServiceProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="HostManagementServices",
            manager=self.manager,
            drivers_status=self.drivers_status,
            drivers_tasks=self.drivers_tasks,
            network_status=self.network_status,
            network_safe_apply=self.network_safe_apply,
            storage_status=self.storage_status,
            storage_mutation=self.storage_mutation,
            users=self.users,
            updates_status=self.updates_status,
            updates_tasks=self.updates_tasks,
            maintenance_status=self.maintenance_status,
            maintenance_systemd=self.maintenance_systemd,
            maintenance_logs=self.maintenance_logs,
            maintenance_time_sync=self.maintenance_time_sync,
            maintenance_power=self.maintenance_power,
            ssh=self.ssh,
            ssh_safe_disable=self.ssh_safe_disable,
        )


@dataclass(slots=True, frozen=True)
class ModelServices:
    model_coordinator: ModelManagerProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    model_parameter_service: ModelParameterServiceProtocol
    model_virtual_model_service: VirtualModelServiceProtocol
    model_provider_coordinator: ModelProviderCoordinatorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelServices",
            model_coordinator=self.model_coordinator,
            model_resolution_service=self.model_resolution_service,
            model_information_service=self.model_information_service,
            model_parameter_service=self.model_parameter_service,
            model_virtual_model_service=self.model_virtual_model_service,
            model_provider_coordinator=self.model_provider_coordinator,
        )
