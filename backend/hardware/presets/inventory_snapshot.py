"""SoAI - GPU inventory snapshot for preset slot storage [backend/hardware/presets/inventory_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from hardware.gpu_info_resolution import (
    build_gpu_info_service_dependencies,
    get_gpu_info_snapshot,
)
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("snapshot_gpu_inventory",)


def snapshot_gpu_inventory(
    executor: CommandExecutorProtocol,
    *,
    detailed_gpu_info: bool,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> dict[str, JSONDict]:
    gpu_info_services = build_gpu_info_service_dependencies(
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
    )
    raw_info = get_gpu_info_snapshot(
        executor,
        detailed=detailed_gpu_info,
        deps=gpu_info_services,
    )
    devices: dict[str, JSONDict] = {}
    gpus = raw_info.get("gpus") if isinstance(raw_info, dict) else None
    if not isinstance(gpus, list):
        return devices
    for entry in gpus:
        if not isinstance(entry, dict):
            continue
        device_id, index_value = (entry.get("device_id"), entry.get("index"))
        if not isinstance(device_id, str) or not device_id:
            continue
        gpu_index = normalize_gpu_index(index_value)
        if gpu_index is None or gpu_index < 0:
            continue
        gpu_name = entry.get("name")
        device_info: JSONDict = {
            "gpu_index": gpu_index,
            "name": gpu_name if isinstance(gpu_name, str) else str(gpu_name),
        }
        vendor = entry.get("vendor")
        if isinstance(vendor, str) and vendor:
            device_info["vendor"] = vendor
        devices[device_id] = device_info
    return devices
