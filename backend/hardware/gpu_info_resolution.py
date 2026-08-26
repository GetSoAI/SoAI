"""SoAI - Standard GPU info resolution with optional pre-fetched payload [backend/hardware/gpu_info_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from hardware.info_gpu import get_gpu_info
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)

__all__ = (
    "GPUInfoServiceDependencies",
    "build_gpu_info_service_dependencies",
    "get_gpu_info_snapshot",
    "get_gpu_info_snapshot_for_services",
    "resolve_gpu_info",
    "resolve_gpu_info_for_services",
)


@dataclass(frozen=True, slots=True)
class GPUInfoServiceDependencies:
    gpu_info_cache_service: GPUInfoCacheServiceProtocol
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol
    nvidia_nvml_gate: NvmlGateProtocol
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GPUInfoServiceDependencies",
            gpu_info_cache_service=self.gpu_info_cache_service,
            gpu_vendor_detection_service=self.gpu_vendor_detection_service,
            nvidia_capabilities_cache_service=self.nvidia_capabilities_cache_service,
            nvidia_nvml_gate=self.nvidia_nvml_gate,
        )


def build_gpu_info_service_dependencies(
    *,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> GPUInfoServiceDependencies:
    return GPUInfoServiceDependencies(
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
    )


def get_gpu_info_snapshot(
    executor: CommandExecutorProtocol,
    *,
    detailed: bool,
    deps: GPUInfoServiceDependencies,
) -> JSONDict:
    return get_gpu_info(
        executor,
        detailed=detailed,
        cache_service=deps.gpu_info_cache_service,
        vendor_detection_service=deps.gpu_vendor_detection_service,
        nvidia_nvml_gate=deps.nvidia_nvml_gate,
        nvidia_capabilities_cache_service=deps.nvidia_capabilities_cache_service,
    )


def get_gpu_info_snapshot_for_services(
    executor: CommandExecutorProtocol,
    *,
    detailed: bool,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> JSONDict:
    return get_gpu_info_snapshot(
        executor,
        detailed=detailed,
        deps=build_gpu_info_service_dependencies(
            gpu_info_cache_service=gpu_info_cache_service,
            gpu_vendor_detection_service=gpu_vendor_detection_service,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        ),
    )


def resolve_gpu_info(
    executor: CommandExecutorProtocol,
    *,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    gpu_info: JSONDict | None,
) -> JSONDict:
    return resolve_gpu_info_for_services(
        executor,
        deps=build_gpu_info_service_dependencies(
            gpu_info_cache_service=gpu_info_cache_service,
            gpu_vendor_detection_service=gpu_vendor_detection_service,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        ),
        gpu_info=gpu_info,
    )


def resolve_gpu_info_for_services(
    executor: CommandExecutorProtocol,
    *,
    deps: GPUInfoServiceDependencies,
    gpu_info: JSONDict | None,
) -> JSONDict:
    if isinstance(gpu_info, dict):
        return gpu_info
    return get_gpu_info_snapshot(
        executor,
        detailed=False,
        deps=deps,
    )
