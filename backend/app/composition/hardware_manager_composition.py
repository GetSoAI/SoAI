"""SoAI - Hardware manager service assembly [backend/app/composition/hardware_manager_composition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.lifecycle.coordinator import LifecycleCoordinator
from core.config.clamped_numeric import read_config_nonnegative_int
from core.errors.exceptions import ValidationError
from core.events.protocols import EventBusProtocol
from core.hardware.protocols import (
    DatabaseHardwareProtocol,
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.hardware.protocols_speed_test import (
    DiskSpeedTestServiceProtocol,
    NetworkSpeedTestServiceProtocol,
)
from core.logging.protocols import TraceLogger
from core.system.command_executor import CommandExecutor
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict
from core.validation.boolean_coercion import coerce_bool_with_default
from hardware.gpu_capabilities_service import GpuCapabilitiesService
from hardware.gpu_info_cache_service import GPUInfoCacheService
from hardware.gpu_tuning.service import HardwareGpuTuningService
from hardware.manager.dependencies import HardwareManagerDependencies, HardwareManagerSettings
from hardware.manager.hardware_manager import HardwareManager
from hardware.monitor import (
    HardwareMonitoringCoordinator,
    HardwareMonitoringCoordinatorDependencies,
)
from hardware.vendor_detection_service import GPUVendorDetectionService

__all__ = ("build_hardware_manager",)


def build_hardware_manager(
    *,
    base_dir: str,
    event_bus: EventBusProtocol | None,
    database_hardware: DatabaseHardwareProtocol | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    hardware_config: JSONDict,
    hardware_gpu_tuning: HardwareGpuTuningService,
    disk_speed_test_service: DiskSpeedTestServiceProtocol,
    network_speed_test_service: NetworkSpeedTestServiceProtocol,
    gpu_info_cache_service: GPUInfoCacheService,
    gpu_vendor_detection_service: GPUVendorDetectionService,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    gpu_capabilities_service: GpuCapabilitiesService,
    hardware_manager_settings: HardwareManagerSettings,
    command_executor: CommandExecutor,
    hardware_logger: TraceLogger,
    lifecycle_coordinator: LifecycleCoordinator,
) -> HardwareManager:
    history_config_obj = coerce_json_dict(hardware_manager_settings.history_config)
    if history_config_obj is None:
        raise ValidationError("Hardware history config must be JSON-compatible.")
    history_enabled = bool(database_hardware) and coerce_bool_with_default(
        history_config_obj.get("ENABLED"),
        default=False,
        strict=False,
    )
    monitoring_coordinator = HardwareMonitoringCoordinator(
        HardwareMonitoringCoordinatorDependencies(
            event_bus=event_bus,
            database_hardware=database_hardware,
            history_enabled=history_enabled,
            retention_hours=read_config_nonnegative_int(
                history_config_obj,
                "DB_RETENTION_HOURS",
                120,
            ),
            logger=hardware_logger,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
        ),
    )
    hardware_manager = HardwareManager(
        HardwareManagerDependencies(
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            config=hardware_config,
            base_path=base_dir,
            event_bus=event_bus,
            database_hardware=database_hardware,
            monitoring_coordinator=monitoring_coordinator,
            hw_gpu_tuning=hardware_gpu_tuning,
            disk_speed_test_service=disk_speed_test_service,
            network_speed_test_service=network_speed_test_service,
            gpu_info_cache_service=gpu_info_cache_service,
            gpu_vendor_detection_service=gpu_vendor_detection_service,
            gpu_capabilities_service=gpu_capabilities_service,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
            settings=hardware_manager_settings,
            command_executor=command_executor,
        ),
    )
    lifecycle_coordinator.register_actor(hardware_manager)
    return hardware_manager
