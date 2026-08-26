"""SoAI - Hardware subsystem services assembly and dependency composition [backend/app/composition/build_hardware.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.composition.hardware_gpu_tuning_composition import build_gpu_tuning_service
from app.composition.hardware_manager_composition import build_hardware_manager
from app.composition.hardware_null_services import build_null_hardware_services
from app.composition.hardware_preset_configuration import (
    coerce_hardware_config,
    resolve_hardware_preset_paths,
)
from app.composition.hardware_slot_storage_loading import load_gpu_slot_storage
from app.composition.hardware_terminal_composition import (
    build_command_executor,
    build_terminal_service,
)
from app.composition.nvidia_nvml_environment import create_nvidia_nvml_environment
from app.lifecycle.coordinator import LifecycleCoordinator
from core.config.protocols import ConfigProtocol
from core.events.protocols import EventBusProtocol
from core.hardware.protocols import (
    DatabaseHardwareProtocol,
    HardwareManagerProtocol,
)
from core.hardware.protocols_speed_test import (
    DiskSpeedTestServiceProtocol,
    NetworkSpeedTestServiceProtocol,
)
from core.logging.trace import get_logger
from core.system.command_executor import CommandExecutor
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.terminal.protocols import TerminalServiceProtocol
from hardware.activity_registry import (
    HardwareActivityRegistry,
    HardwareActivityRegistryDependencies,
)
from hardware.gpu_capabilities_service import (
    GpuCapabilitiesService,
    GpuCapabilitiesServiceDependencies,
)
from hardware.gpu_info_cache_service import (
    GPUInfoCacheService,
    GPUInfoCacheServiceDependencies,
)
from hardware.gpu_tuning.null_service import NullHardwareGpuTuningService
from hardware.gpu_tuning.service import HardwareGpuTuningService
from hardware.manager.settings_factory import resolve_hardware_manager_settings
from hardware.vendor_detection_service import (
    GPUVendorDetectionService,
    GPUVendorDetectionServiceDependencies,
)
from hardware.vendors.nvidia.nvml_preflight import probe_nvml_runtime

if TYPE_CHECKING:
    from core.runtime.flags_service import RuntimeFlagsService

__all__ = ("build_hardware_services",)

LOGGER_NAME = "SoAI.app.composition.build_hardware"


def build_hardware_services(
    *,
    hardware_available: bool,
    config: ConfigProtocol,
    base_dir: str,
    event_bus: EventBusProtocol | None,
    database_hardware: DatabaseHardwareProtocol | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    lifecycle_coordinator: LifecycleCoordinator,
    runtime_flags: RuntimeFlagsService,
    disk_speed_test_service: DiskSpeedTestServiceProtocol,
    network_speed_test_service: NetworkSpeedTestServiceProtocol,
) -> tuple[
    TerminalServiceProtocol,
    HardwareGpuTuningService | NullHardwareGpuTuningService,
    HardwareManagerProtocol,
    CommandExecutor | None,
    HardwareActivityRegistry,
]:
    activity_registry = HardwareActivityRegistry(HardwareActivityRegistryDependencies())
    if not hardware_available:
        terminal_service, tuning, manager, command_executor = build_null_hardware_services(
            runtime_flags=runtime_flags,
            lifecycle_coordinator=lifecycle_coordinator,
        )
        return (terminal_service, tuning, manager, command_executor, activity_registry)

    hardware_config = coerce_hardware_config(config)
    hardware_logger = get_logger(LOGGER_NAME)
    command_executor = build_command_executor()
    gpu_vendor_detection_service = GPUVendorDetectionService(
        GPUVendorDetectionServiceDependencies(
            logger=hardware_logger,
            command_executor=command_executor,
        ),
    )
    gpu_info_cache_service = GPUInfoCacheService(GPUInfoCacheServiceDependencies())
    nvidia_environment = create_nvidia_nvml_environment(
        nvml_runtime_status=probe_nvml_runtime(),
    )
    nvidia_nvml_gate = nvidia_environment.nvml_gate
    nvidia_capabilities_cache_service = nvidia_environment.capabilities_cache_service
    hardware_manager_settings = resolve_hardware_manager_settings(
        config_dict=hardware_config,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
    )
    gpu_capabilities_service = GpuCapabilitiesService(
        GpuCapabilitiesServiceDependencies(
            cache_ttl_seconds=hardware_manager_settings.cache_ttl,
            command_executor=command_executor,
            gpu_info_cache_service=gpu_info_cache_service,
            gpu_vendor_detection_service=gpu_vendor_detection_service,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
            operation="hardware.get_gpu_capabilities.probe",
            thread_name="soai-gpu-capabilities",
            logger=hardware_logger,
        ),
    )
    gpu_operation_lock = asyncio.Lock()
    terminal = build_terminal_service(
        terminal_enabled=config.get_bool("SERVER.WEBUI.TERMINAL.ENABLED"),
        base_dir=base_dir,
        hardware_logger=hardware_logger,
        command_executor=command_executor,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        runtime_flags=runtime_flags,
        lifecycle_coordinator=lifecycle_coordinator,
    )
    gpu_slots_path, dirty_flag_path, detailed_gpu_info = resolve_hardware_preset_paths(
        config=config,
        base_dir=base_dir,
        hardware_config=hardware_config,
    )
    gpu_slot_storage = load_gpu_slot_storage(
        gpu_slots_path=gpu_slots_path,
        hardware_logger=hardware_logger,
        command_executor=command_executor,
        detailed_gpu_info=detailed_gpu_info,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
    )
    hardware_gpu_tuning = build_gpu_tuning_service(
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        command_executor=command_executor,
        hardware_config=hardware_config,
        base_dir=base_dir,
        detailed_gpu_info=detailed_gpu_info,
        event_bus=event_bus,
        hardware_logger=hardware_logger,
        gpu_slot_storage=gpu_slot_storage,
        gpu_slots_path=gpu_slots_path,
        dirty_flag_path=dirty_flag_path,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        gpu_capabilities_service=gpu_capabilities_service,
        gpu_operation_lock=gpu_operation_lock,
        activity_registry=activity_registry,
        runtime_flags=runtime_flags,
        lifecycle_coordinator=lifecycle_coordinator,
    )
    hardware_manager = build_hardware_manager(
        base_dir=base_dir,
        event_bus=event_bus,
        database_hardware=database_hardware,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        hardware_config=hardware_config,
        hardware_gpu_tuning=hardware_gpu_tuning,
        disk_speed_test_service=disk_speed_test_service,
        network_speed_test_service=network_speed_test_service,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        gpu_capabilities_service=gpu_capabilities_service,
        hardware_manager_settings=hardware_manager_settings,
        command_executor=command_executor,
        hardware_logger=hardware_logger,
        lifecycle_coordinator=lifecycle_coordinator,
    )
    return (
        terminal,
        hardware_gpu_tuning,
        hardware_manager,
        command_executor,
        activity_registry,
    )
