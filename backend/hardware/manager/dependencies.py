"""SoAI - HardwareManager dependencies dataclass [backend/hardware/manager/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.hardware.protocols import (
    DatabaseHardwareProtocol,
    HardwareGpuTuningProtocol,
    HardwareMonitoringCoordinatorProtocol,
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.hardware.protocols_speed_test import (
    DiskSpeedTestServiceProtocol,
    NetworkSpeedTestServiceProtocol,
)
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
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "HardwareManagerDependencies",
    "HardwareManagerSettings",
)


@dataclass(frozen=True, slots=True)
class HardwareManagerSettings:
    enabled: bool
    monitoring_interval_ms: int
    cache_ttl: float
    detailed_gpu_info: bool
    min_specs_enabled: bool
    network_speed_cache_ttl_seconds: float
    history_config: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True)
class HardwareManagerDependencies:
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    config: JSONDict
    base_path: str | None
    event_bus: EventBusProtocol | None
    database_hardware: DatabaseHardwareProtocol | None
    monitoring_coordinator: HardwareMonitoringCoordinatorProtocol
    hw_gpu_tuning: HardwareGpuTuningProtocol
    disk_speed_test_service: DiskSpeedTestServiceProtocol
    network_speed_test_service: NetworkSpeedTestServiceProtocol
    gpu_info_cache_service: GPUInfoCacheServiceProtocol
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol
    gpu_capabilities_service: GpuCapabilitiesServiceProtocol
    nvidia_nvml_gate: NvmlGateProtocol
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol
    settings: HardwareManagerSettings
    command_executor: CommandExecutorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="HardwareManagerDependencies",
            cancellation_binder=self.cancellation_binder,
            command_executor=self.command_executor,
            config=self.config,
            disk_speed_test_service=self.disk_speed_test_service,
            finalizer_tracker=self.finalizer_tracker,
            gpu_capabilities_service=self.gpu_capabilities_service,
            gpu_info_cache_service=self.gpu_info_cache_service,
            gpu_vendor_detection_service=self.gpu_vendor_detection_service,
            hw_gpu_tuning=self.hw_gpu_tuning,
            monitoring_coordinator=self.monitoring_coordinator,
            network_speed_test_service=self.network_speed_test_service,
            nvidia_capabilities_cache_service=self.nvidia_capabilities_cache_service,
            nvidia_nvml_gate=self.nvidia_nvml_gate,
            settings=self.settings,
        )
