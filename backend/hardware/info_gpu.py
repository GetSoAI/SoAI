"""SoAI - GPU detection and monitoring for NVIDIA, AMD, and Intel [backend/hardware/info_gpu.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.hardware.gpu_inventory_errors import GPUObservationSupersededError
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from core.timing.monotonic import monotonic_ms
from hardware.gpu_inventory.darwin_inventory import read_darwin_gpu_inventory
from hardware.gpu_inventory.linux_merge import merge_linux_gpu_inventory
from hardware.gpu_inventory.linux_pci import read_linux_pci_gpu_inventory
from hardware.gpu_inventory.linux_platform import read_linux_platform_gpu_inventory
from hardware.gpu_inventory.payloads import build_gpu_payload, simplify_gpu_payload
from hardware.gpu_inventory.physical_observations import gpu_inventory_sources_incomplete
from hardware.gpu_inventory.sensor_observations import reconcile_gpu_sensor_observations
from hardware.gpu_inventory.vulkan_physical_acquisition import observe_vulkan_gpu_capabilities
from hardware.gpu_inventory.windows_capacity_observations import (
    reconcile_windows_capacity_observations,
)
from hardware.gpu_inventory.windows_inventory import (
    collect_windows_gpu_inventory,
)
from hardware.gpu_observation import GPUInfoObservation, capture_gpu_info_observation
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.vendors.amd.adl_session import AdlRuntime
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
    from core.errors.exceptions import SoAIError
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "get_gpu_info",
    "get_gpu_observation",
    "log_gpu_tool_warnings",
)

LOGGER_NAME = "SoAI.hardware.info_gpu"


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
            "AMD GPU detected, but 'amd-smi' tool not found. AMD SMI monitoring requires the AMD SMI tools.",
        )
    if (
        (runtime_platform.is_linux or runtime_platform.is_windows)
        and INTEL_VENDOR in detected_vendors
        and (not is_xpu_smi_available())
    ):
        xpu_smi_path = resolve_xpu_smi_path()
        logger.info(
            "Intel GPU detected, but '%s' tool not found. XPU-SMI monitoring requires the Intel management tools and compatible drivers.",
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
    adl_runtime: AdlRuntime | None = None,
) -> JSONDict:
    return get_gpu_observation(
        executor,
        detailed=detailed,
        cache_service=cache_service,
        vendor_detection_service=vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        adl_runtime=adl_runtime,
    ).payload


def get_gpu_observation(
    executor: CommandExecutorProtocol,
    *,
    detailed: bool = True,
    cache_service: GPUInfoCacheServiceProtocol,
    vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    adl_runtime: AdlRuntime | None = None,
) -> GPUInfoObservation:
    runtime_platform = get_runtime_platform()
    cache_key = bool(detailed)

    def acquire_observation(probe_revision: int, acquisition_sequence: int) -> GPUInfoObservation:
        all_gpus: list[JSONDict] = []
        all_drivers: JSONDict = {}
        display_adapters: list[JSONDict] = []
        inventory_sources: JSONDict | None = None
        acquisition_diagnostics: list[SoAIError] = []
        detected_vendors = vendor_detection_service.get_system_gpu_vendors()
        vendor_hints = vendor_hints_or_all(detected_vendors)
        if runtime_platform.is_windows:
            retained_capacity = cache_service.get_retained_observation()
            inventory = collect_windows_gpu_inventory(
                executor,
                detailed=detailed,
                vendor_hints=vendor_hints,
                nvidia_nvml_gate=nvidia_nvml_gate,
                nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
                adl_runtime=adl_runtime,
            )
            reconcile_windows_capacity_observations(
                inventory.gpus, retained_capacity.payload if retained_capacity is not None else None
            )
            all_gpus.extend(inventory.gpus)
            all_drivers.update(inventory.compute_drivers)
            display_adapters = inventory.display_adapters
            inventory_sources = inventory.source_states
        elif runtime_platform.is_macos:
            darwin_inventory = read_darwin_gpu_inventory(executor)
            all_gpus.extend(darwin_inventory.gpus)
            inventory_sources = {
                "darwin": {
                    "state": darwin_inventory.state.value,
                    "reason_code": darwin_inventory.reason_code,
                }
            }
        elif runtime_platform.is_linux:
            platform_inventory = read_linux_platform_gpu_inventory(sysfs_root="/sys")
            acquisition_diagnostics.extend(platform_inventory.diagnostics)
            pci_inventory = read_linux_pci_gpu_inventory(
                executor, drm_pci_slots=platform_inventory.pci_drm_slots
            )
            acquisition_diagnostics.extend(pci_inventory.acquisition.diagnostics)
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
                ([], {})
                if INTEL_VENDOR not in vendor_hints
                else query_intel_gpus(executor, detailed)
            )
            telemetry_gpus = [*nvidia_gpus, *amd_gpus, *intel_gpus]
            all_gpus.extend(
                merge_linux_gpu_inventory(
                    [*pci_inventory.gpus, *platform_inventory.gpus],
                    telemetry_gpus,
                    pci_acquisition=pci_inventory.acquisition,
                )
            )
            display_adapters = [
                *pci_inventory.display_adapters,
                *platform_inventory.display_adapters,
            ]
            inventory_sources = {
                "linux_pci": {
                    "state": pci_inventory.acquisition.state.value,
                    "reason_code": pci_inventory.acquisition.reason_code,
                },
                "linux_platform": {
                    "state": platform_inventory.state.value,
                    "reason_code": platform_inventory.reason_code,
                },
            }
            all_drivers.update(nvidia_drivers)
            all_drivers.update(amd_drivers)
            all_drivers.update(intel_drivers)
        observe_vulkan_gpu_capabilities(all_gpus)
        payload = build_gpu_payload(all_gpus, all_drivers, display_adapters)
        simplified_payload = simplify_gpu_payload(payload) if not detailed else payload
        if inventory_sources is not None:
            simplified_payload["inventory_sources"] = copy.deepcopy(inventory_sources)
        with cache_service.lock:
            if probe_revision != cache_service.revision():
                raise GPUObservationSupersededError("GPU inventory observation was superseded.")
            if not cache_service.is_current_acquisition(cache_key, acquisition_sequence):
                replacement = cache_service.get_cached_observation(
                    cache_key, monotonic_ms() / 1000.0
                )
                if replacement is None:
                    raise TimeoutError("GPU inventory observation was superseded.")
                return replacement
            retained = cache_service.get_retained_observation()
            rows = simplified_payload.get("gpus")
            if isinstance(rows, list):
                reconcile_gpu_sensor_observations(
                    [row for row in rows if isinstance(row, dict)],
                    retained.payload if retained is not None else None,
                )
            incomplete = gpu_inventory_sources_incomplete(
                simplified_payload,
                retained_payload=retained.payload if retained is not None else None,
            )
            if incomplete:
                if retained is not None:
                    retained_payload = retained.payload
                    retained_payload["inventory_sources"] = copy.deepcopy(inventory_sources)
                    return GPUInfoObservation(
                        retained_payload,
                        retained.observed_at_ms,
                        False,
                        True,
                        diagnostics=tuple(acquisition_diagnostics),
                    )
                return GPUInfoObservation(
                    copy.deepcopy(simplified_payload),
                    (
                        capture_gpu_info_observation(simplified_payload).observed_at_ms
                        if isinstance(rows, list) and rows
                        else None
                    ),
                    False,
                    True,
                    diagnostics=tuple(acquisition_diagnostics),
                    coverage_complete=False,
                )
            accepted_monotonic = monotonic_ms() / 1000.0
            accepted = cache_service.publish_acquisition(
                cache_key,
                accepted_monotonic,
                simplified_payload,
                revision=probe_revision,
                sequence=acquisition_sequence,
            )
            return GPUInfoObservation(
                accepted.payload, accepted.observed_at_ms, not incomplete, False
            )

    return cache_service.acquire_observation(
        cache_key, acquire_observation, monotonic_clock_ms=monotonic_ms
    )
