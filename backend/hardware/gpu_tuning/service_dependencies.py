"""SoAI - GPU tuning shared service dependency bundle [backend/hardware/gpu_tuning/service_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.logging.protocols import TraceLogger
from core.logging.rate_limited_logger import RateLimitedLogger
from core.system.protocols import CommandExecutorProtocol
from hardware.gpu_inventory.executable_resolution import (
    GpuExecutableResolution,
    require_gpu_executable_selector,
)
from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.vendors.amd.adl_session import AdlRuntime
from hardware.vendors.nvidia.smi import NvidiaSettingsController

__all__ = (
    "GPUStartupAcquisitionResources",
    "GpuServiceDependencies",
    "require_startup_acquisition_resources",
)


@dataclass(frozen=True, slots=True)
class GpuServiceDependencies:
    gpu_info_cache_service: GPUInfoCacheServiceProtocol
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol
    nvidia_nvml_gate: NvmlGateProtocol
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol
    nvidia_settings_controller: NvidiaSettingsController | None
    nvidia_smi_executable: GpuExecutableResolution
    intel_executable: GpuExecutableResolution
    adl_runtime: AdlRuntime | None = None
    slot_observation_diagnostics: RateLimitedLogger = field(
        default_factory=lambda: RateLimitedLogger(interval_seconds=30.0)
    )

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GpuServiceDependencies",
            gpu_info_cache_service=self.gpu_info_cache_service,
            gpu_vendor_detection_service=self.gpu_vendor_detection_service,
            nvidia_capabilities_cache_service=self.nvidia_capabilities_cache_service,
            nvidia_nvml_gate=self.nvidia_nvml_gate,
            nvidia_smi_executable=self.nvidia_smi_executable,
            intel_executable=self.intel_executable,
            slot_observation_diagnostics=self.slot_observation_diagnostics,
        )
        require_gpu_executable_selector(self.nvidia_smi_executable, executable="nvidia-smi")
        require_gpu_executable_selector(self.intel_executable, executable="xpu-smi")


@dataclass(frozen=True, slots=True)
class GPUStartupAcquisitionResources:
    executor: CommandExecutorProtocol
    logger: TraceLogger
    gpu_services: GpuServiceDependencies

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GPUStartupAcquisitionResources",
            executor=self.executor,
            logger=self.logger,
            gpu_services=self.gpu_services,
        )
        if not isinstance(self.gpu_services, GpuServiceDependencies):
            raise ValidationError("GPU startup acquisition requires concrete shared resources.")


def require_startup_acquisition_resources(
    scope: GPUControlStartupScope | None, resources: GPUStartupAcquisitionResources | None
) -> None:
    if scope is None:
        if resources is not None:
            raise ValidationError(
                "GPU ordinary control cannot carry startup acquisition authority."
            )
    elif not isinstance(resources, GPUStartupAcquisitionResources):
        raise ValidationError("GPU startup requires its concrete acquisition resources.")
