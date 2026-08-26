"""SoAI - Bootstrap stage application state assembly [backend/app/composition/application_bootstrap_state_assembly.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from httpx2 import AsyncClient

from app.application_dependencies import ApplicationPaths, ApplicationSecurity
from app.composition.application_bootstrap_state import ApplicationBootstrapState
from app.composition.bootstrap_state_assembly_dependencies import (
    BootstrapStateAssemblyDependencies,
)
from app.composition.build_application_bootstrap_core import CoreBootstrapStage
from app.composition.build_bootstrap_state_assembly import (
    assemble_application_bootstrap_state,
)
from app.composition.build_core_services import build_domain_event_delivery
from app.composition.build_tasks import TaskRegistryFactoryResult
from app.config.service import ConfigManager
from app.edition_composition import EditionComposition
from app.types_services_database import DatabaseServices
from core.hardware.protocols import HardwareGpuTuningProtocol, HardwareManagerProtocol
from core.hardware.protocols_activity import HardwareActivityRegistryProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.openai.token_counter import PromptTokenCounter
from core.orchestrator.routing_config import RoutingConfig
from core.state.protocols import StateAggregatorProtocol
from core.system.protocols import CommandExecutorProtocol
from core.terminal.protocols import TerminalServiceProtocol

__all__ = ("assemble_bootstrap_state_and_finalize",)


def assemble_bootstrap_state_and_finalize(
    *,
    core_stage: CoreBootstrapStage,
    paths: ApplicationPaths,
    security: ApplicationSecurity,
    database_services: DatabaseServices,
    config_manager: ConfigManager,
    routing_config: RoutingConfig,
    task_registry_result: TaskRegistryFactoryResult,
    http_client: AsyncClient,
    hardware_manager: HardwareManagerProtocol,
    hardware_gpu_tuning: HardwareGpuTuningProtocol,
    hardware_activity_registry: HardwareActivityRegistryProtocol,
    terminal: TerminalServiceProtocol,
    storage_manager: StorageManagerProtocol,
    prompt_token_counter: PromptTokenCounter,
    command_executor: CommandExecutorProtocol | None,
    metrics_manager: MetricsManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    edition_composition: EditionComposition,
) -> ApplicationBootstrapState:
    assembly_deps = BootstrapStateAssemblyDependencies(
        runtime_foundation=core_stage.runtime_foundation,
        configuration_foundation=core_stage.configuration_foundation,
        task_type_routing_service=core_stage.task_type_routing_service,
        event_bus=core_stage.event_bus,
        log_manager=core_stage.log_manager,
        logging_instance=core_stage.logging_instance,
        restart_state_manager=core_stage.restart_state_manager,
        paths=paths,
        security=security,
        database_services=database_services,
        config_manager=config_manager,
        task_registry_result=task_registry_result,
        cancellation_system=core_stage.runtime_foundation.cancellation_system,
        config=core_stage.configuration_foundation.config,
        domain_event_delivery=build_domain_event_delivery(
            config=core_stage.configuration_foundation.config,
        ),
        metrics_manager=metrics_manager,
        state_aggregator=state_aggregator,
        http_client=http_client,
        hardware_manager=hardware_manager,
        hardware_gpu_tuning=hardware_gpu_tuning,
        hardware_activity_registry=hardware_activity_registry,
        terminal=terminal,
        storage_manager=storage_manager,
        prompt_token_counter=prompt_token_counter,
        command_executor=command_executor,
        files=core_stage.configuration_foundation.files,
        routing_config=routing_config,
        runtime_flags_service=core_stage.configuration_foundation.runtime_flags_service,
        edition_composition=edition_composition,
    )
    return assemble_application_bootstrap_state(assembly_deps)
