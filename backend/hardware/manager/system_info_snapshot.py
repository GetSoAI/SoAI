"""SoAI - Hardware system snapshot collection [backend/hardware/manager/system_info_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING

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
from hardware.gpu_info_resolution import get_gpu_observation_for_services
from hardware.gpu_inventory.physical_observations import gpu_inventory_sources_incomplete
from hardware.gpu_observation import GPUInfoObservation
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
from hardware.manager.component_observations import (
    OPTIONAL_PROBE_EXCEPTIONS,
    observed_status,
    require_component_value,
    require_observation_status,
    unavailable_status,
)
from hardware.manager.system_info_cache import SYSTEM_INFO_COMPONENT_ORDER
from hardware.monitoring.disk_speed_snapshot import get_disk_speed_snapshot
from hardware.monitoring.network_speed import get_network_speed
from hardware.probe import sync_get_raw_capabilities
from hardware.storage.disk_info import DiskInventoryResult, get_disk_info
from hardware.vendors.amd.adl_session import AdlRuntime
from hardware.vendors.nvidia.smi import NvidiaSettingsController

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
    nvidia_settings_controller: NvidiaSettingsController | None,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    rapl_energy_cache: RaplEnergyCache,
    components: Sequence[str] | None,
    current_time_ms: int,
    manager: SystemInfoSnapshotManagerProtocol,
    include_gpu_capabilities: bool,
    failures: dict[str, Exception] | None = None,
    adl_runtime: AdlRuntime | None = None,
    windows_static_inventory: JSONDict | None = None,
) -> JSONDict:
    info_components: JSONDict = {}
    component_status: JSONDict = {}
    network_observation: JSONDict = {}
    component_funcs: dict[
        str, Callable[[], JSONValue | DiskInventoryResult | GPUInfoObservation]
    ] = {
        "uptime": get_uptime_info,
        "os": lambda: cached_os_info,
        "cpus": lambda: get_cpu_info(executor, rapl_energy_cache=rapl_energy_cache),
        "memory": get_memory_info,
        "swap": get_swap_info,
        "gpu": lambda: get_gpu_observation_for_services(
            executor,
            detailed=detailed_gpu_info,
            gpu_info_cache_service=gpu_info_cache_service,
            gpu_vendor_detection_service=gpu_vendor_detection_service,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
            adl_runtime=adl_runtime,
        ),
        "disk": lambda: get_disk_info(executor),
        "disk_speed": lambda: get_disk_speed_snapshot(manager) or {},
        "motherboard": lambda: get_motherboard_info(executor),
        "network": manager.get_network_info,
        "network_speed": lambda: get_network_speed(manager, observation_status=network_observation),
    }
    static_statuses: JSONDict = {}
    if windows_static_inventory is not None:
        raw_statuses = windows_static_inventory.get("component_status")
        static_statuses = raw_statuses if isinstance(raw_statuses, dict) else {}
        cpu_inventory = windows_static_inventory.get("cpus")
        cached_cpus = (
            [cpu for cpu in cpu_inventory if isinstance(cpu, dict)]
            if isinstance(cpu_inventory, list)
            else []
        )
        network_inventory = windows_static_inventory.get("network")
        adapter_names: JSONValue = (
            network_inventory.get("visible_adapter_names")
            if isinstance(network_inventory, dict)
            else []
        )
        visible_names = (
            [name for name in adapter_names if isinstance(name, str)]
            if isinstance(adapter_names, list)
            else []
        )
        component_funcs.update(
            {
                "cpus": lambda: get_cpu_info(
                    executor,
                    rapl_energy_cache=rapl_energy_cache,
                    windows_inventory=cached_cpus,
                ),
                "motherboard": lambda: windows_static_inventory.get("motherboard", {}),
                "network": lambda: get_network_info(
                    executor, windows_visible_adapter_names=visible_names
                ),
                "network_speed": lambda: get_network_speed(
                    manager,
                    visible_adapter_names=visible_names,
                    observation_status=network_observation,
                ),
            }
        )
    requested_components = set(components or component_funcs.keys())
    if "cpu" in requested_components:
        requested_components.add("cpus")
    for component, component_func in component_funcs.items():
        if component in requested_components:
            try:
                value = component_func()
                if isinstance(value, GPUInfoObservation):
                    require_component_value(component, value.payload)
                    info_components[component] = value.payload
                    gpu_status = observed_status(current_time_ms)
                    gpu_status["observed_at_ms"] = value.observed_at_ms
                    gpu_status["sampled_current"] = value.sampled_current
                    if value.inventory_revision is not None and value.valid_until_ms is not None:
                        gpu_status["inventory_revision"] = value.inventory_revision
                        gpu_status["valid_until_ms"] = value.valid_until_ms
                    if value.refresh_failed:
                        gpu_rows = value.payload.get("gpus")
                        gpu_status["status"] = (
                            "partial"
                            if not value.coverage_complete
                            and isinstance(gpu_rows, list)
                            and gpu_rows
                            else "stale" if value.observed_at_ms is not None else "unavailable"
                        )
                        gpu_status["error_code"] = "monitoring_probe_unavailable"
                    else:
                        if gpu_inventory_sources_incomplete(value.payload):
                            gpu_status["status"] = "partial"
                            gpu_status["sampled_current"] = False
                            gpu_status["error_code"] = "monitoring_probe_unavailable"
                    require_observation_status(gpu_status)
                    component_status[component] = gpu_status
                elif isinstance(value, DiskInventoryResult):
                    info_components[component] = value.entries
                    disk_status: JSONDict = {
                        "status": "available" if value.status == "complete" else value.status,
                        "checked_at_ms": int(current_time_ms),
                        "sampled_current": value.status != "unavailable",
                        "failed_item_count": value.failed_item_count,
                        "diagnostics": [
                            {
                                "scope": item.scope,
                                "reason": item.reason,
                                "item_index": item.item_index,
                            }
                            for item in value.diagnostics
                        ],
                    }
                    disk_status["observed_at_ms"] = (
                        int(current_time_ms) if value.status != "unavailable" else None
                    )
                    if value.diagnostics:
                        disk_status["error_code"] = f"storage_inventory_{value.status}"
                    require_observation_status(disk_status)
                    component_status[component] = disk_status
                else:
                    if component == "os" and value is None:
                        component_status[component] = unavailable_status(
                            current_time_ms, error_code="monitoring_probe_unavailable"
                        )
                        continue
                    require_component_value(component, value)
                    info_components[component] = value
                    native_state = (
                        value.get("windows_inventory_status") if isinstance(value, dict) else None
                    )
                    component_status[component] = observed_status(
                        current_time_ms,
                        status=(
                            native_state
                            if native_state in ("partial", "unavailable")
                            else "available"
                        ),
                    )
                    inventory_status = static_statuses.get(component)
                    if isinstance(inventory_status, dict):
                        require_observation_status(inventory_status)
                        if component == "motherboard":
                            board_status = deepcopy(inventory_status)
                            board_status["sampled_current"] = False
                            component_status[component] = board_status
                        else:
                            dynamic_status = observed_status(current_time_ms)
                            if inventory_status["status"] not in ("available", "partial"):
                                dynamic_status.update(deepcopy(inventory_status))
                                dynamic_status["checked_at_ms"] = current_time_ms
                                dynamic_status["sampled_current"] = False
                            component_status[component] = dynamic_status
            except OPTIONAL_PROBE_EXCEPTIONS as exception:
                component_status[component] = unavailable_status(
                    current_time_ms, error_code="monitoring_probe_unavailable"
                )
                if failures is not None:
                    failures[component] = exception
    for component in ("disk_speed", "network_speed"):
        value = info_components.get(component)
        if not isinstance(value, dict):
            continue
        samples = (
            list(value.values())
            if component == "network_speed" and "observed_at_ms" not in value
            else [value]
        )
        observed_times: list[int] = []
        for sample in samples:
            timestamp = sample.get("observed_at_ms") if isinstance(sample, dict) else None
            if isinstance(timestamp, int) and not isinstance(timestamp, bool):
                observed_times.append(timestamp)
        if observed_times:
            speed_status = observed_status(
                current_time_ms,
                status="available" if len(observed_times) == len(samples) else "partial",
            )
            speed_status["observed_at_ms"] = min(observed_times)
            speed_status["sampled_current"] = False
            component_status[component] = speed_status
        else:
            component_status[component] = unavailable_status(
                current_time_ms, error_code="monitoring_sample_unavailable"
            )
    if network_observation:
        require_observation_status(network_observation)
        component_status["network_speed"] = network_observation
    gpu_snapshot = info_components.get("gpu")
    gpu_component_status = component_status.get("gpu")
    if (
        include_gpu_capabilities
        and isinstance(gpu_snapshot, dict)
        and isinstance(gpu_component_status, dict)
        and gpu_component_status.get("status") in ("available", "partial")
    ):
        try:
            capabilities = sync_get_raw_capabilities(
                executor,
                gpu_info_cache_service=gpu_info_cache_service,
                gpu_vendor_detection_service=gpu_vendor_detection_service,
                nvidia_nvml_gate=nvidia_nvml_gate,
                nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
                gpu_info=gpu_snapshot,
                nvidia_settings_controller=nvidia_settings_controller,
                adl_runtime=adl_runtime,
                logger=logger,
            )
            capabilities = hw_gpu_tuning.enrich_gpu_capabilities(capabilities)
            if isinstance(capabilities, dict) and is_success_payload(
                capabilities,
                logger,
                operation="hardware.manager.system_info_snapshot.is_success_payload",
                recover_message="Failed to parse success flag (non-critical).",
            ):
                enriched_gpu = deepcopy(gpu_snapshot)
                merge_capabilities_into_gpu_snapshot(enriched_gpu, capabilities)
                info_components["gpu"] = enriched_gpu
                component_status["gpu_capabilities"] = observed_status(current_time_ms)
            else:
                component_status["gpu_capabilities"] = unavailable_status(
                    current_time_ms, error_code="gpu_capabilities_unavailable"
                )
        except OPTIONAL_PROBE_EXCEPTIONS as exception:
            component_status["gpu_capabilities"] = unavailable_status(
                current_time_ms, error_code="gpu_capabilities_unavailable"
            )
            if failures is not None:
                failures["gpu_capabilities"] = exception
    final_ordered_info: JSONDict = {"timestamp_ms": int(current_time_ms)}
    for component_name in SYSTEM_INFO_COMPONENT_ORDER:
        if component_name in info_components:
            final_ordered_info[component_name] = info_components[component_name]
    if component_status:
        final_ordered_info["component_status"] = component_status
    cpus_value = final_ordered_info.get("cpus")
    if isinstance(cpus_value, list) and cpus_value:
        first_cpu = cpus_value[0]
        if isinstance(first_cpu, dict):
            final_ordered_info["cpu"] = first_cpu
            component_status["cpu"] = component_status["cpus"]
    return final_ordered_info
