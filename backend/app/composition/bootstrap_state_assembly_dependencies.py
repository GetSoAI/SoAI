"""SoAI - Application bootstrap state assembly dependencies [backend/app/composition/bootstrap_state_assembly_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.composition.bootstrap_state_core import BootstrapStateCore
from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from app.composition.build_cancellation_system import CancellationSystem
    from app.composition.build_tasks import TaskRegistryFactoryResult
    from app.edition_composition import EditionComposition
    from core.config.runtime_config import Config
    from core.events.protocols import DurableEventDeliveryProtocol
    from core.hardware.protocols import (
        HardwareGpuTuningProtocol,
        HardwareManagerProtocol,
    )
    from core.hardware.protocols_activity import HardwareActivityRegistryProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.orchestrator.routing_config import RoutingConfig
    from core.plugins.protocols_instance import FilesProtocol
    from core.runtime.protocols import RuntimeFlagsMutationProtocol
    from core.state.protocols import StateAggregatorProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.terminal.protocols import TerminalServiceProtocol

__all__ = ("BootstrapStateAssemblyDependencies",)


@dataclass(frozen=True, slots=True)
class BootstrapStateAssemblyDependencies(BootstrapStateCore):
    task_registry_result: TaskRegistryFactoryResult
    cancellation_system: CancellationSystem
    config: Config
    domain_event_delivery: DurableEventDeliveryProtocol
    metrics_manager: MetricsManagerProtocol
    state_aggregator: StateAggregatorProtocol
    http_client: AsyncClient
    hardware_manager: HardwareManagerProtocol
    hardware_gpu_tuning: HardwareGpuTuningProtocol
    hardware_activity_registry: HardwareActivityRegistryProtocol
    terminal: TerminalServiceProtocol
    storage_manager: StorageManagerProtocol
    prompt_token_counter: PromptTokenCounter
    command_executor: CommandExecutorProtocol | None
    files: FilesProtocol
    routing_config: RoutingConfig
    runtime_flags_service: RuntimeFlagsMutationProtocol
    edition_composition: EditionComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="BootstrapStateAssemblyDependencies",
            cancellation_system=self.cancellation_system,
            config=self.config,
            domain_event_delivery=self.domain_event_delivery,
            edition_composition=self.edition_composition,
            files=self.files,
            hardware_gpu_tuning=self.hardware_gpu_tuning,
            hardware_activity_registry=self.hardware_activity_registry,
            hardware_manager=self.hardware_manager,
            http_client=self.http_client,
            metrics_manager=self.metrics_manager,
            prompt_token_counter=self.prompt_token_counter,
            routing_config=self.routing_config,
            runtime_flags_service=self.runtime_flags_service,
            state_aggregator=self.state_aggregator,
            storage_manager=self.storage_manager,
            task_registry_result=self.task_registry_result,
            terminal=self.terminal,
        )
