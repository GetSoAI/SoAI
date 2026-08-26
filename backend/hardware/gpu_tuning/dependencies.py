"""SoAI - GPU tuning dependencies [backend/hardware/gpu_tuning/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
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
from hardware.internal_protocols import (
    GpuCapabilitiesServiceProtocol,
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)

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
    gpu_operation_lock: asyncio.Lock
    activity_registry: HardwareActivityRegistryProtocol
    runtime_flags: RuntimeFlagsViewProtocol

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
        )
