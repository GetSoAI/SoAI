"""SoAI - Bootstrap stage hardware and metrics composition [backend/app/composition/application_bootstrap_hardware_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.application_dependencies import ApplicationEnvironment
from app.composition.bootstrap_requirements import require_initialized_dependency
from app.composition.build_cancellation_system import CancellationSystem
from app.composition.build_hardware import build_hardware_services
from app.composition.build_metrics import build_metrics_and_state_services
from app.composition.build_runtime import RuntimeFoundation
from app.internal_protocols import MetricsAwareEventBusProtocol
from app.types_services_database import DatabaseServices
from core.config.runtime_config import Config
from core.hardware.protocols import (
    HardwareGpuTuningProtocol,
    HardwareManagerProtocol,
)
from core.hardware.protocols_storage import StorageManagerProtocol
from core.hardware.speed_test.disk_service import DiskSpeedTestService
from core.hardware.speed_test.network_service import NetworkSpeedTestService
from core.metrics.protocols import MetricsManagerProtocol
from core.openai.token_counter import PromptTokenCounter
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.flags_service import RuntimeFlagsService
from core.runtime.state_store import RuntimeStateStore
from core.state.protocols import StateAggregatorProtocol
from core.system.protocols import CommandExecutorProtocol
from core.terminal.protocols import TerminalServiceProtocol
from hardware.activity_registry import HardwareActivityRegistry

__all__ = (
    "HardwareAndMetricsServices",
    "build_hardware_and_metrics_services",
)


@dataclass(frozen=True, slots=True)
class HardwareAndMetricsServices:
    terminal: TerminalServiceProtocol
    hardware_gpu_tuning: HardwareGpuTuningProtocol
    hardware_manager: HardwareManagerProtocol
    command_executor: CommandExecutorProtocol | None
    hardware_activity_registry: HardwareActivityRegistry
    metrics_manager: MetricsManagerProtocol
    state_aggregator: StateAggregatorProtocol
    storage_manager: StorageManagerProtocol
    prompt_token_counter: PromptTokenCounter


def build_hardware_and_metrics_services(
    *,
    environment: ApplicationEnvironment,
    runtime_state: RuntimeStateStore,
    config: Config,
    files: FilesProtocol,
    runtime_flags_service: RuntimeFlagsService,
    event_bus: MetricsAwareEventBusProtocol,
    database_services: DatabaseServices,
    cancellation_system: CancellationSystem,
    runtime_foundation: RuntimeFoundation,
    disk_speed_test_service: DiskSpeedTestService,
    network_speed_test_service: NetworkSpeedTestService,
) -> HardwareAndMetricsServices:
    (
        terminal,
        hardware_gpu_tuning,
        hardware_manager,
        command_executor,
        hardware_activity_registry,
    ) = build_hardware_services(
        hardware_available=runtime_state.hardware_manager_available,
        config=config,
        base_dir=environment.base_dir,
        event_bus=event_bus,
        database_hardware=require_initialized_dependency(
            database_services.hardware,
            "Database hardware",
        ),
        cancellation_binder=cancellation_system.binder,
        finalizer_tracker=cancellation_system.finalizer_tracker,
        lifecycle_coordinator=runtime_foundation.lifecycle_coordinator,
        runtime_flags=runtime_flags_service,
        disk_speed_test_service=disk_speed_test_service,
        network_speed_test_service=network_speed_test_service,
    )
    (
        metrics_manager,
        state_aggregator,
        storage_manager,
        prompt_token_counter,
    ) = build_metrics_and_state_services(
        config=config,
        files=files,
        base_dir=environment.base_dir,
        event_bus=event_bus,
        database_writer=require_initialized_dependency(
            database_services.core,
            "Database core",
        ).writer,
        database_metrics=require_initialized_dependency(
            database_services.metrics,
            "Database metrics",
        ),
        database_hardware=require_initialized_dependency(
            database_services.hardware,
            "Database hardware",
        ),
        database_plugins=require_initialized_dependency(
            database_services.plugins,
            "Database plugins",
        ),
        cancellation_binder=cancellation_system.binder,
        finalizer_tracker=cancellation_system.finalizer_tracker,
        lifecycle_coordinator=runtime_foundation.lifecycle_coordinator,
    )
    return HardwareAndMetricsServices(
        terminal=terminal,
        hardware_gpu_tuning=hardware_gpu_tuning,
        hardware_manager=hardware_manager,
        command_executor=command_executor,
        hardware_activity_registry=hardware_activity_registry,
        metrics_manager=metrics_manager,
        state_aggregator=state_aggregator,
        storage_manager=storage_manager,
        prompt_token_counter=prompt_token_counter,
    )
