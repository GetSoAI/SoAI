"""SoAI - Hardware system snapshot collection [backend/hardware/manager/system_info_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ProcessError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.protocols import (
    HardwareGpuTuningProtocol,
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.logging.protocols import TraceLogger
from core.system.protocols import CommandExecutorProtocol
from core.validation.runtime import is_success_payload
from hardware.cpu_rapl import RaplEnergyCache
from hardware.gpu_capabilities.aggregate_payloads import (
    merge_capabilities_into_gpu_snapshot,
)
from hardware.gpu_info_resolution import get_gpu_info_snapshot_for_services
from hardware.info_cpu import get_cpu_info
from hardware.info_memory import get_memory_info, get_swap_info
from hardware.info_motherboard import get_motherboard_info
from hardware.info_network import get_network_info
from hardware.info_system import get_uptime_info
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
    SystemInfoSnapshotManagerProtocol,
)
from hardware.manager.system_info_cache import SYSTEM_INFO_COMPONENT_ORDER
from hardware.monitoring.disk_speed_snapshot import get_disk_speed_snapshot
from hardware.monitoring.network_speed import get_network_speed
from hardware.probe import sync_get_raw_capabilities
from hardware.storage.disk_info import get_disk_info

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("collect_system_info_snapshot",)


def collect_system_info_snapshot(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    hw_gpu_tuning: HardwareGpuTuningProtocol,
    cached_os_info: JSONDict | None,
    detailed_gpu_info: bool,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    rapl_energy_cache: RaplEnergyCache,
    components: Sequence[str] | None,
    current_time_ms: int,
    manager: SystemInfoSnapshotManagerProtocol,
    include_gpu_capabilities: bool,
) -> JSONDict:
    info_components: JSONDict = {}
    component_funcs: dict[str, Callable[[], JSONValue]] = {
        "uptime": get_uptime_info,
        "os": lambda: cached_os_info,
        "cpus": lambda: get_cpu_info(executor, rapl_energy_cache=rapl_energy_cache),
        "memory": get_memory_info,
        "swap": get_swap_info,
        "gpu": lambda: get_gpu_info_snapshot_for_services(
            executor,
            detailed=detailed_gpu_info,
            gpu_info_cache_service=gpu_info_cache_service,
            gpu_vendor_detection_service=gpu_vendor_detection_service,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        ),
        "disk": lambda: get_disk_info(executor),
        "disk_speed": lambda: get_disk_speed_snapshot(manager) or {},
        "motherboard": lambda: get_motherboard_info(executor),
        "network": get_network_info,
        "network_speed": lambda: get_network_speed(manager),
    }
    requested_components = set(components or component_funcs.keys())
    if "cpu" in requested_components:
        requested_components.add("cpus")
    for component, component_func in component_funcs.items():
        if component in requested_components:
            try:
                info_components[component] = component_func()
            except RECOVERABLE_EXCEPTIONS as exception:
                raise ProcessError(
                    f"Failed to collect '{component}' system information.",
                    details={"component": component, "reason": str(exception)},
                ) from exception
    gpu_snapshot = info_components.get("gpu")
    if include_gpu_capabilities and isinstance(gpu_snapshot, dict):
        try:
            capabilities = sync_get_raw_capabilities(
                executor,
                gpu_info_cache_service=gpu_info_cache_service,
                gpu_vendor_detection_service=gpu_vendor_detection_service,
                nvidia_nvml_gate=nvidia_nvml_gate,
                nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
                gpu_info=gpu_snapshot,
                logger=logger,
            )
            capabilities = hw_gpu_tuning.enrich_gpu_capabilities(capabilities)
            if isinstance(capabilities, dict) and is_success_payload(
                capabilities,
                logger,
                operation="hardware.manager.system_info_snapshot.is_success_payload",
                recover_message="Failed to parse success flag (non-critical).",
            ):
                merge_capabilities_into_gpu_snapshot(gpu_snapshot, capabilities)
        except RECOVERABLE_EXCEPTIONS as exception:
            raise ProcessError(
                "Failed to merge GPU capabilities into hardware snapshot.",
                details={"reason": str(exception)},
            ) from exception
    final_ordered_info: JSONDict = {"timestamp_ms": int(current_time_ms)}
    for component_name in SYSTEM_INFO_COMPONENT_ORDER:
        if component_name in info_components:
            final_ordered_info[component_name] = info_components[component_name]
    cpus_value = final_ordered_info.get("cpus")
    if isinstance(cpus_value, list) and cpus_value:
        first_cpu = cpus_value[0]
        if isinstance(first_cpu, dict):
            final_ordered_info["cpu"] = first_cpu
    return final_ordered_info
