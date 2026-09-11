"""SoAI - GPU tuning shared service dependency bundle [backend/hardware/gpu_tuning/service_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.vendors.nvidia.smi import NvidiaSettingsController

__all__ = ("GpuServiceDependencies",)


@dataclass(frozen=True, slots=True)
class GpuServiceDependencies:
    gpu_info_cache_service: GPUInfoCacheServiceProtocol
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol
    nvidia_nvml_gate: NvmlGateProtocol
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol
    nvidia_settings_controller: NvidiaSettingsController | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GpuServiceDependencies",
            gpu_info_cache_service=self.gpu_info_cache_service,
            gpu_vendor_detection_service=self.gpu_vendor_detection_service,
            nvidia_capabilities_cache_service=self.nvidia_capabilities_cache_service,
            nvidia_nvml_gate=self.nvidia_nvml_gate,
        )
