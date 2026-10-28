"""SoAI - GPU tuning dependencies [backend/hardware/gpu_tuning/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.events.protocols import EventBusProtocol
from core.hardware.protocols import (
    GpuSlotStorageManagerProtocol,
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.hardware.protocols_activity import HardwareActivityRegistryProtocol
from core.logging.protocols import TraceLogger
from core.system.protocols import CommandExecutorProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from hardware.gpu_inventory.executable_resolution import (
    GpuExecutableResolution,
    require_gpu_executable_selector,
)
from hardware.gpu_tuning.control_operation_delivery import GPUControlDeliveryDependencies
from hardware.gpu_tuning.control_operations import GPUControlOperationState
from hardware.gpu_tuning.native_control_recovery import NativeControlRecovery
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.internal_protocols import (
    GpuCapabilitiesServiceProtocol,
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.vendors.amd.adl_session import AdlRuntime
from hardware.vendors.nvidia.smi import NvidiaSettingsController

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict

__all__ = ("HardwareGpuTuningServiceDependencies",)


@dataclass(frozen=True, slots=True)
class HardwareGpuTuningServiceDependencies:
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    command_executor: CommandExecutorProtocol
    config_dict: JSONDict
    base_dir: str
    detailed_gpu_info: bool
    event_bus: EventBusProtocol | None
    logger: TraceLogger
    gpu_slot_storage: GpuSlotStorageManagerProtocol
    gpu_slots_path: str
    dirty_flag_path: str
    gpu_capabilities_service: GpuCapabilitiesServiceProtocol
    gpu_info_cache_service: GPUInfoCacheServiceProtocol
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol
    nvidia_nvml_gate: NvmlGateProtocol
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol
    nvidia_settings_controller: NvidiaSettingsController | None
    gpu_operation_lock: asyncio.Lock
    activity_registry: HardwareActivityRegistryProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    nvidia_smi_executable: GpuExecutableResolution
    intel_executable: GpuExecutableResolution
    native_control_recovery: NativeControlRecovery
    control_operation_state: GPUControlOperationState
    adl_runtime: AdlRuntime | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="HardwareGpuTuningServiceDependencies",
            activity_registry=self.activity_registry,
            base_dir=self.base_dir,
            cancellation_binder=self.cancellation_binder,
            command_executor=self.command_executor,
            config_dict=self.config_dict,
            detailed_gpu_info=self.detailed_gpu_info,
            dirty_flag_path=self.dirty_flag_path,
            finalizer_tracker=self.finalizer_tracker,
            gpu_capabilities_service=self.gpu_capabilities_service,
            gpu_info_cache_service=self.gpu_info_cache_service,
            gpu_slot_storage=self.gpu_slot_storage,
            gpu_slots_path=self.gpu_slots_path,
            gpu_vendor_detection_service=self.gpu_vendor_detection_service,
            gpu_operation_lock=self.gpu_operation_lock,
            logger=self.logger,
            nvidia_capabilities_cache_service=self.nvidia_capabilities_cache_service,
            nvidia_nvml_gate=self.nvidia_nvml_gate,
            runtime_flags=self.runtime_flags,
            nvidia_smi_executable=self.nvidia_smi_executable,
            intel_executable=self.intel_executable,
            native_control_recovery=self.native_control_recovery,
            control_operation_state=self.control_operation_state,
        )
        require_gpu_executable_selector(self.nvidia_smi_executable, executable="nvidia-smi")
        require_gpu_executable_selector(self.intel_executable, executable="xpu-smi")
        if not isinstance(self.control_operation_state, GPUControlOperationState):
            raise ValidationError("GPU operation dependency requires its concrete state owner.")
        operation_dependencies = self.control_operation_state.dependencies
        if (
            operation_dependencies.activity_registry is not self.activity_registry
            or operation_dependencies.operation_lock is not self.gpu_operation_lock
            or operation_dependencies.logger is not self.logger
            or operation_dependencies.finalizer_tracker is not self.finalizer_tracker
        ):
            raise ValidationError("GPU operation state must share service resource owners.")


@dataclass(frozen=True, slots=True)
class GpuSettingsApplyDependencies:
    executor: CommandExecutorProtocol
    logger: TraceLogger
    storage: GpuSlotStorageManagerProtocol
    detailed_gpu_info: bool
    nvidia_settings_controller: NvidiaSettingsController | None
    gpu_services: GpuServiceDependencies
    native_control_recovery: NativeControlRecovery
    control_operation_state: GPUControlOperationState
    delivery_dependencies: GPUControlDeliveryDependencies
    runtime_flags: RuntimeFlagsViewProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GpuSettingsApplyDependencies",
            detailed_gpu_info=self.detailed_gpu_info,
            executor=self.executor,
            gpu_services=self.gpu_services,
            logger=self.logger,
            storage=self.storage,
            native_control_recovery=self.native_control_recovery,
            control_operation_state=self.control_operation_state,
            delivery_dependencies=self.delivery_dependencies,
            runtime_flags=self.runtime_flags,
        )
        if not isinstance(self.native_control_recovery, NativeControlRecovery):
            raise ValidationError("GPU apply requires its concrete recovery authority.")
        if not isinstance(self.control_operation_state, GPUControlOperationState):
            raise ValidationError("GPU apply requires its concrete operation owner.")
        if not isinstance(self.delivery_dependencies, GPUControlDeliveryDependencies):
            raise ValidationError("GPU apply requires its concrete delivery authority.")
        recovery = self.native_control_recovery.dependencies
        operation = self.control_operation_state.dependencies
        delivery = self.delivery_dependencies
        shared_effect_authority = (
            recovery.storage is self.storage
            and delivery.executor is self.executor
            and recovery.dirty_flag_path == delivery.effects.dirty_flag_path
            and delivery.effects.gpu_services is self.gpu_services
        )
        shared_terminal_owners = (
            delivery.logger is self.logger
            and operation.logger is self.logger
            and operation.finalizer_tracker is delivery.finalizer_tracker
        )
        if not shared_effect_authority or not shared_terminal_owners:
            raise ValidationError("GPU apply authorities must share the same resource owners.")
