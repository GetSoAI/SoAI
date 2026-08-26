"""SoAI - GPU device ID resolution [backend/hardware/manager/gpu_device_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.system.protocols import CommandExecutorProtocol
from hardware.gpu_info_resolution import get_gpu_info_snapshot_for_services
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("resolve_gpu_device_id",)


def resolve_gpu_device_id(
    gpu_index: int,
    executor: CommandExecutorProtocol,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> str | None:
    gpu_snapshot = get_gpu_info_snapshot_for_services(
        executor,
        detailed=False,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
    )
    gpus_value: JSONValue | None = gpu_snapshot.get("gpus")
    if not isinstance(gpus_value, list) or not gpus_value:
        return None
    gpus: list[JSONDict] = [entry for entry in gpus_value if isinstance(entry, dict)]
    for entry in gpus:
        if isinstance(entry, dict) and entry.get("index") == gpu_index:
            device_id = entry.get("device_id")
            return device_id if isinstance(device_id, str) else None
    return None
