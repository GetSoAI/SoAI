"""SoAI - Hardware manager cached system info query [backend/hardware/manager/system_info_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from hardware.info_system import get_os_info
from hardware.manager.manager_state import HardwareManagerState
from hardware.manager.system_capabilities import sync_get_system_capabilities
from hardware.manager.system_info_cache import (
    build_cached_response,
    build_final_ordered_info,
    build_summary,
    resolve_needed_keys,
)
from hardware.manager.system_info_snapshot import collect_system_info_snapshot
from hardware.vendors.nvidia.smi import NvidiaSettingsController

if TYPE_CHECKING:
    from core.hardware.protocols import (
        HardwareGpuTuningProtocol,
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue
    from hardware.cpu_rapl import RaplEnergyCache
    from hardware.internal_protocols import (
        GPUInfoCacheServiceProtocol,
        GPUVendorDetectionServiceProtocol,
        SystemInfoSnapshotManagerProtocol,
    )

__all__ = ("sync_query_system_info",)

NETWORK_COMPONENT_KEY = "network"
TIMESTAMP_KEY = "timestamp_ms"


def sync_query_system_info(
    *,
    state: HardwareManagerState,
    manager: SystemInfoSnapshotManagerProtocol,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    hw_gpu_tuning: HardwareGpuTuningProtocol,
    cache_ttl_seconds: float,
    monitoring_interval_ms: int,
    history_config: Mapping[str, JSONValue],
    history_enabled: bool,
    detailed_gpu_info: bool,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_settings_controller: NvidiaSettingsController | None,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    rapl_energy_cache: RaplEnergyCache,
    components: Sequence[str] | None,
    cache: bool,
    include_gpu_capabilities: bool,
) -> JSONDict:
    if state.monitoring_stop_event.is_set():
        return state.last_full_info.copy() if state.last_full_info else {}
    if not cache and include_gpu_capabilities:
        gpu_info_cache_service.invalidate_cache()
    now_monotonic = time.monotonic()
    now_ts_ms = int(epoch_ms())
    with state.cache_lock:
        cached_keys = set[str](state.last_full_info.keys()) if state.last_full_info else set[str]()
        needed_keys = resolve_needed_keys(components)
        if (
            cache
            and state.last_full_info
            and (now_monotonic - state.last_update_time_monotonic < cache_ttl_seconds)
            and needed_keys.issubset(cached_keys)
        ):
            if components:
                return build_cached_response(
                    last_full_info=state.last_full_info,
                    components=components,
                )
            return state.last_full_info.copy()
        if not state.os_info:
            state.os_info = get_os_info()
        cached_os_info = state.os_info.copy() if state.os_info else None
        detailed_gpu_flag = detailed_gpu_info
        network_query_sequence: int | None = None
        if NETWORK_COMPONENT_KEY in needed_keys:
            state.issued_network_query_sequence += 1
            network_query_sequence = state.issued_network_query_sequence
    base_snapshot = collect_system_info_snapshot(
        executor=executor,
        logger=logger,
        hw_gpu_tuning=hw_gpu_tuning,
        cached_os_info=cached_os_info,
        detailed_gpu_info=detailed_gpu_flag,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        rapl_energy_cache=rapl_energy_cache,
        nvidia_settings_controller=nvidia_settings_controller,
        components=components,
        current_time_ms=now_ts_ms,
        manager=manager,
        include_gpu_capabilities=include_gpu_capabilities,
    )
    gpu_snapshot = base_snapshot.get("gpu")
    summary = build_summary(base_snapshot=base_snapshot)
    capabilities_payload = sync_get_system_capabilities(
        executor=executor,
        logger=logger,
        monitoring_interval_ms=monitoring_interval_ms,
        history_config=history_config,
        history_enabled=history_enabled,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        rapl_energy_cache=rapl_energy_cache,
        gpu_info=gpu_snapshot if isinstance(gpu_snapshot, dict) else None,
    )
    final_ordered_info = build_final_ordered_info(
        base_snapshot=base_snapshot,
        summary=summary,
        capabilities_payload=capabilities_payload,
    )
    with state.cache_lock:
        _merge_into_cache(
            state=state,
            final_ordered_info=final_ordered_info,
            network_query_sequence=network_query_sequence,
            now_monotonic=now_monotonic,
        )
    return final_ordered_info


def _merge_into_cache(
    *,
    state: HardwareManagerState,
    final_ordered_info: JSONDict,
    network_query_sequence: int | None,
    now_monotonic: float,
) -> None:
    merged_cache = state.last_full_info.copy() if state.last_full_info else {}
    network_result_superseded = (
        network_query_sequence is not None
        and network_query_sequence <= state.committed_network_query_sequence
    )
    if network_result_superseded:
        previous_timestamp_ms = merged_cache.get(TIMESTAMP_KEY)
        merged_cache.update(
            {
                key: value
                for key, value in final_ordered_info.items()
                if key != NETWORK_COMPONENT_KEY
            },
        )
        new_timestamp_ms = merged_cache.get(TIMESTAMP_KEY)
        if isinstance(previous_timestamp_ms, int) and isinstance(new_timestamp_ms, int):
            merged_cache[TIMESTAMP_KEY] = max(previous_timestamp_ms, new_timestamp_ms)
        state.last_update_time_monotonic = max(state.last_update_time_monotonic, now_monotonic)
    else:
        merged_cache.update(final_ordered_info)
        if network_query_sequence is not None:
            state.committed_network_query_sequence = network_query_sequence
        state.last_update_time_monotonic = now_monotonic
    cpus_value = merged_cache.get("cpus")
    if isinstance(cpus_value, list) and cpus_value:
        first_cpu = cpus_value[0]
        merged_cache["cpu"] = first_cpu if isinstance(first_cpu, dict) else {}
    state.last_full_info = merged_cache
