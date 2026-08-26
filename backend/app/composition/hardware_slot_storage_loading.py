"""SoAI - Hardware GPU slot storage loading and pruning [backend/app/composition/hardware_slot_storage_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.logging.protocols import LoggerProtocol
from core.system.command_executor import CommandExecutor
from hardware.gpu_info_cache_service import GPUInfoCacheService
from hardware.presets.slot_payload_loading import load_gpu_slots_payload
from hardware.presets.slot_storage import (
    GpuSlotStorageManager,
    GpuSlotStorageManagerDependencies,
)
from hardware.vendor_detection_service import GPUVendorDetectionService

__all__ = ("load_gpu_slot_storage",)


def load_gpu_slot_storage(
    *,
    gpu_slots_path: str,
    hardware_logger: LoggerProtocol,
    command_executor: CommandExecutor,
    detailed_gpu_info: bool,
    gpu_info_cache_service: GPUInfoCacheService,
    gpu_vendor_detection_service: GPUVendorDetectionService,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> GpuSlotStorageManager:
    gpu_slot_storage = GpuSlotStorageManager(
        GpuSlotStorageManagerDependencies(
            path=gpu_slots_path,
            logger=hardware_logger,
        ),
    )
    load_gpu_slots_payload(
        gpu_slot_storage,
        command_executor,
        detailed_gpu_info=detailed_gpu_info,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        prune=True,
        allow_create=True,
    )
    return gpu_slot_storage
