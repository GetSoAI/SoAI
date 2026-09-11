"""SoAI - Hardware GPU tuning service assembly [backend/app/composition/hardware_gpu_tuning_composition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.lifecycle.coordinator import LifecycleCoordinator
from core.events.protocols import EventBusProtocol
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.logging.protocols import TraceLogger
from core.system.command_executor import CommandExecutor
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.types.json import JSONDict
from hardware.activity_registry import HardwareActivityRegistry
from hardware.gpu_capabilities_service import GpuCapabilitiesService
from hardware.gpu_info_cache_service import GPUInfoCacheService
from hardware.gpu_tuning.dependencies import HardwareGpuTuningServiceDependencies
from hardware.gpu_tuning.service import HardwareGpuTuningService
from hardware.presets.slot_storage import GpuSlotStorageManager
from hardware.vendor_detection_service import GPUVendorDetectionService
from hardware.vendors.nvidia.smi import (
    NvidiaSettingsController,
    NvidiaSettingsControllerDependencies,
)

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("build_gpu_tuning_service",)


def build_gpu_tuning_service(
    *,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    command_executor: CommandExecutor,
    hardware_config: JSONDict,
    base_dir: str,
    detailed_gpu_info: bool,
    event_bus: EventBusProtocol | None,
    hardware_logger: TraceLogger,
    gpu_slot_storage: GpuSlotStorageManager,
    gpu_slots_path: str,
    dirty_flag_path: str,
    gpu_info_cache_service: GPUInfoCacheService,
    gpu_vendor_detection_service: GPUVendorDetectionService,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_settings_controller: NvidiaSettingsController | None,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    gpu_capabilities_service: GpuCapabilitiesService,
    gpu_operation_lock: asyncio.Lock,
    activity_registry: HardwareActivityRegistry,
    runtime_flags: RuntimeFlagsViewProtocol,
    lifecycle_coordinator: LifecycleCoordinator,
) -> HardwareGpuTuningService:
    hardware_gpu_tuning = HardwareGpuTuningService(
        HardwareGpuTuningServiceDependencies(
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            command_executor=command_executor,
            config_dict=hardware_config,
            base_dir=base_dir,
            detailed_gpu_info=detailed_gpu_info,
            event_bus=event_bus,
            logger=hardware_logger,
            gpu_slot_storage=gpu_slot_storage,
            gpu_slots_path=gpu_slots_path,
            dirty_flag_path=dirty_flag_path,
            gpu_capabilities_service=gpu_capabilities_service,
            gpu_info_cache_service=gpu_info_cache_service,
            gpu_vendor_detection_service=gpu_vendor_detection_service,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_settings_controller=nvidia_settings_controller,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
            gpu_operation_lock=gpu_operation_lock,
            activity_registry=activity_registry,
            runtime_flags=runtime_flags,
        ),
    )
    lifecycle_coordinator.register_actor(hardware_gpu_tuning)
    return hardware_gpu_tuning


def create_nvidia_settings_controller(
    controller_logger: TraceLogger,
    nvml_gate: NvmlGateProtocol,
) -> NvidiaSettingsController | None:
    if not (nvml_gate.runtime_platform.is_linux and nvml_gate.nvidia_settings_available):
        return None
    controller = NvidiaSettingsController(
        NvidiaSettingsControllerDependencies(logger=controller_logger)
    )
    controller_logger.trace("nvidia-settings controller initialized for Linux NVIDIA GPU control")
    return controller
