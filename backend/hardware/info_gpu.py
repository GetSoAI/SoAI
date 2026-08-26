"""SoAI - GPU detection and monitoring for NVIDIA, AMD, and Intel [backend/hardware/info_gpu.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from core.timing.monotonic import monotonic_ms
from hardware.gpu_inventory.linux_merge import merge_linux_gpu_inventory
from hardware.gpu_inventory.linux_pci import read_linux_pci_gpu_inventory
from hardware.gpu_inventory.payloads import build_gpu_payload, simplify_gpu_payload
from hardware.gpu_inventory.windows_inventory import (
    collect_windows_gpu_inventory,
)
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.vendors.amd.availability import is_amd_smi_available
from hardware.vendors.amd.gpu_info import get_amd_gpu_info
from hardware.vendors.intel.gpu_info import query_intel_gpus
from hardware.vendors.intel.runtime import is_xpu_smi_available, resolve_xpu_smi_path
from hardware.vendors.nvidia.query import resolve_query_nvidia_gpus
from hardware.vendors.vendor_types import (
    AMD_VENDOR,
    INTEL_VENDOR,
    NVIDIA_VENDOR,
    vendor_hints_or_all,
)

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "get_gpu_info",
    "log_gpu_tool_warnings",
)

LOGGER_NAME = "SoAI.hardware.info_gpu"


def _payload_has_gpus(payload: JSONDict) -> bool:
    gpus_value = payload.get("gpus")
    return isinstance(gpus_value, list) and any(isinstance(entry, dict) for entry in gpus_value)


def log_gpu_tool_warnings(
    vendor_detection_service: GPUVendorDetectionServiceProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    runtime_platform = get_runtime_platform()
    detected_vendors = vendor_detection_service.get_system_gpu_vendors()
    if not detected_vendors:
        logger.trace("Could not detect any specific GPU vendors during preliminary scan.")
        return
    if (
        AMD_VENDOR in detected_vendors
        and (not is_amd_smi_available())
        and runtime_platform.is_linux
    ):
        logger.info(
            "AMD GPU detected, but 'amd-smi' tool not found. Monitoring/control will be unavailable. Please install the AMD SMI tools for full functionality.",
        )
    if INTEL_VENDOR in detected_vendors and (not is_xpu_smi_available()):
        xpu_smi_path = resolve_xpu_smi_path()
        logger.info(
            "Intel GPU detected, but '%s' tool not found. Monitoring/control will be unavailable. Please install the official Intel drivers and management tools for your GPU.",
            xpu_smi_path,
        )


def get_gpu_info(
    executor: CommandExecutorProtocol,
    *,
    detailed: bool = True,
    cache_service: GPUInfoCacheServiceProtocol,
    vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    runtime_platform = get_runtime_platform()
    cache_key = bool(detailed)
    now = monotonic_ms() / 1000.0
    cached_payload = cache_service.get_cached(cache_key, now)
    if cached_payload is not None:
        return copy.deepcopy(cached_payload)
    all_gpus: list[JSONDict] = []
    all_drivers: JSONDict = {}
    display_adapters: list[JSONDict] = []
    detected_vendors = vendor_detection_service.get_system_gpu_vendors()
    vendor_hints = vendor_hints_or_all(detected_vendors)
    if runtime_platform.is_windows:
        inventory = collect_windows_gpu_inventory(
            executor,
            detailed=detailed,
            vendor_hints=vendor_hints,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        )
        all_gpus.extend(inventory.gpus)
        all_drivers.update(inventory.compute_drivers)
        display_adapters = inventory.display_adapters
    else:
        pci_inventory = read_linux_pci_gpu_inventory(executor)
        nvidia_gpus: list[JSONDict] = []
        nvidia_drivers: JSONDict = {}
        if NVIDIA_VENDOR not in vendor_hints:
            nvidia_gpus, nvidia_drivers = ([], {})
        else:
            query_nvidia_gpus = resolve_query_nvidia_gpus()
            nvidia_gpus, nvidia_drivers = query_nvidia_gpus(
                detailed,
                nvml_gate=nvidia_nvml_gate,
                capabilities_cache_service=nvidia_capabilities_cache_service,
            )
        amd_gpus, amd_drivers = (
            ([], {})
            if AMD_VENDOR not in vendor_hints
            else get_amd_gpu_info(executor, detailed, index_offset=0)
        )
        intel_gpus, intel_drivers = (
            ([], {}) if INTEL_VENDOR not in vendor_hints else query_intel_gpus(executor, detailed)
        )
        telemetry_gpus = [*nvidia_gpus, *amd_gpus, *intel_gpus]
        all_gpus.extend(merge_linux_gpu_inventory(pci_inventory.gpus, telemetry_gpus))
        display_adapters = pci_inventory.display_adapters
        all_drivers.update(nvidia_drivers)
        all_drivers.update(amd_drivers)
        all_drivers.update(intel_drivers)
    payload = build_gpu_payload(all_gpus, all_drivers, display_adapters)
    simplified_payload = simplify_gpu_payload(payload) if not detailed else payload
    if detected_vendors and not _payload_has_gpus(simplified_payload):
        cached_gpu_payload = cache_service.get_cached_with_gpus(now)
        if cached_gpu_payload is not None:
            logger.warning(
                "GPU inventory probe returned no GPUs while vendors are detected; using cached non-empty GPU inventory.",
            )
            return cached_gpu_payload
        logger.warning(
            "GPU inventory probe returned no GPUs while vendors are detected; skipping empty GPU inventory cache update.",
        )
        return copy.deepcopy(simplified_payload)
    cache_service.set_cached(cache_key, now, simplified_payload)
    return copy.deepcopy(simplified_payload)
