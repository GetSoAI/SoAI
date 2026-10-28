"""SoAI - Hardware manager cached system info query [backend/hardware/manager/system_info_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.logging.rate_limited_logger import RateLimitedLogger
from core.timing.epoch import epoch_ms
from hardware.info_system import get_os_info
from hardware.manager.component_observations import (
    OPTIONAL_PROBE_EXCEPTIONS,
    accept_component_observations,
    component_statuses,
    disconnected_snapshot,
    is_current_observation_sample,
    observations_reusable,
    observed_status,
    unavailable_status,
)
from hardware.manager.manager_state import HardwareManagerState
from hardware.manager.system_capabilities import (
    build_sampled_system_capabilities,
    read_system_capability_environment,
)
from hardware.manager.system_info_cache import (
    build_cached_response,
    build_final_ordered_info,
    build_summary,
    resolve_needed_keys,
)
from hardware.manager.system_info_snapshot import collect_system_info_snapshot
from hardware.vendors.amd.adl_session import AdlRuntime
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

OPERATION_HARDWARE_COMPONENT_OBSERVATION = "hardware.component_observation"


__all__ = ("sync_query_system_info",)


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
    adl_runtime: AdlRuntime | None = None,
    windows_static_inventory: JSONDict | None = None,
) -> JSONDict:
    now_monotonic = time.monotonic()
    now_ts_ms = int(epoch_ms())
    needed_keys = resolve_needed_keys(components) - {"cpu", "timestamp_ms"}
    if include_gpu_capabilities and "gpu" in needed_keys:
        needed_keys.add("gpu_capabilities")
    with state.cache_lock:
        if state.monitoring_stop_event.is_set():
            return disconnected_snapshot(state.last_full_info)
        if cache and observations_reusable(
            state.component_observations,
            needed_keys,
            now_monotonic=now_monotonic,
            cache_ttl_seconds=cache_ttl_seconds,
        ):
            return _accepted_response(state, components)
        sequences: dict[str, int] = {}
        for component in needed_keys - {"summary", "capabilities"}:
            sequence = state.issued_component_sequences.get(component, 0) + 1
            state.issued_component_sequences[component] = sequence
            sequences[component] = sequence
        if "network" in sequences:
            state.issued_network_query_sequence = sequences["network"]
        cached_os_info = state.os_info.copy() if state.os_info else None
        os_observation = state.component_observations.get("os")
        cached_os_observed_at = (
            os_observation.metadata.get("observed_at_ms")
            if os_observation is not None and cached_os_info is not None
            else None
        )
    if not cache and include_gpu_capabilities:
        gpu_info_cache_service.request_refresh()
    failures: dict[str, Exception] = {}
    if "os" in needed_keys and cached_os_info is None:
        try:
            cached_os_info = get_os_info()
        except OPTIONAL_PROBE_EXCEPTIONS as exception:
            failures["os"] = exception
    try:
        environment = read_system_capability_environment(
            executor=executor,
            logger=logger,
            monitoring_interval_ms=monitoring_interval_ms,
            history_config=history_config,
            history_enabled=history_enabled,
        )
    except OPTIONAL_PROBE_EXCEPTIONS as exception:
        environment = None
        failures["capabilities"] = exception
    base_snapshot = collect_system_info_snapshot(
        executor=executor,
        logger=logger,
        hw_gpu_tuning=hw_gpu_tuning,
        cached_os_info=cached_os_info,
        detailed_gpu_info=detailed_gpu_info,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        rapl_energy_cache=rapl_energy_cache,
        nvidia_settings_controller=nvidia_settings_controller,
        adl_runtime=adl_runtime,
        components=components,
        current_time_ms=now_ts_ms,
        manager=manager,
        include_gpu_capabilities=include_gpu_capabilities,
        failures=failures,
        windows_static_inventory=windows_static_inventory,
    )
    statuses = component_statuses(base_snapshot)
    base_snapshot["component_status"] = statuses
    os_status = statuses.get("os")
    if isinstance(os_status, dict) and isinstance(cached_os_observed_at, int):
        os_status["observed_at_ms"] = cached_os_observed_at
        os_status["sampled_current"] = False
    if "os" in failures:
        base_snapshot.pop("os", None)
        statuses["os"] = unavailable_status(now_ts_ms, error_code="monitoring_probe_unavailable")
    reports: list[tuple[str, Exception, int]] = []
    with state.cache_lock:
        if state.monitoring_stop_event.is_set():
            return disconnected_snapshot(state.last_full_info)
        accepted = accept_component_observations(
            cached=state.last_full_info,
            observations=state.component_observations,
            sequences=sequences,
            snapshot=base_snapshot,
            checked_monotonic=now_monotonic,
            checked_at_ms=now_ts_ms,
        )
        if windows_static_inventory is not None:
            for component in accepted & {"cpus", "network", "motherboard"}:
                candidate_status = statuses.get(component)
                if (
                    not isinstance(candidate_status, dict)
                    or candidate_status["status"] == "unavailable"
                ):
                    continue
                state.component_observations[component].metadata = deepcopy(candidate_status)
                component_statuses(state.last_full_info)[component] = deepcopy(candidate_status)
                if component in base_snapshot and candidate_status["status"] == "stale":
                    state.last_full_info[component] = deepcopy(base_snapshot[component])
            cpus = state.last_full_info.get("cpus")
            if "cpus" in accepted and isinstance(cpus, list) and cpus:
                state.last_full_info["cpu"] = deepcopy(cpus[0])
                component_statuses(state.last_full_info)["cpu"] = deepcopy(
                    state.component_observations["cpus"].metadata
                )
        if "os" in accepted and cached_os_info is not None:
            state.os_info = deepcopy(cached_os_info)
        if "network" in accepted:
            state.committed_network_query_sequence = sequences["network"]
        if accepted or not sequences:
            previous_timestamp = state.last_full_info.get("timestamp_ms")
            derived_checked_at_ms = max(
                previous_timestamp if isinstance(previous_timestamp, int) else 0, now_ts_ms
            )
            state.last_full_info["timestamp_ms"] = derived_checked_at_ms
            state.last_update_time_monotonic = max(state.last_update_time_monotonic, now_monotonic)
            merged = _accepted_response(state, None, current_components=accepted)
            merged_statuses = component_statuses(merged)
            merged_statuses["summary"] = _derived_status(
                merged, ("memory", "gpu"), derived_checked_at_ms
            )
            merged_statuses["capabilities"] = (
                unavailable_status(
                    derived_checked_at_ms, error_code="monitoring_capabilities_unavailable"
                )
                if environment is None
                else _derived_status(merged, ("cpus", "memory", "gpu"), derived_checked_at_ms)
            )
            derived = build_final_ordered_info(
                base_snapshot=merged,
                summary=build_summary(base_snapshot=merged),
                capabilities_payload=(
                    build_sampled_system_capabilities(environment, merged)
                    if environment is not None
                    else {}
                ),
            )
            derived_sequences: dict[str, int] = {}
            for component in ("summary", "capabilities"):
                sequence = state.issued_component_sequences.get(component, 0) + 1
                state.issued_component_sequences[component] = sequence
                derived_sequences[component] = sequence
            sequences.update(derived_sequences)
            accepted.update(
                accept_component_observations(
                    cached=state.last_full_info,
                    observations=state.component_observations,
                    sequences=derived_sequences,
                    snapshot=derived,
                    checked_monotonic=max(state.last_update_time_monotonic, now_monotonic),
                    checked_at_ms=derived_checked_at_ms,
                )
            )
        for component, probe_failure in failures.items():
            if component not in accepted:
                continue
            if component not in state.component_diagnostic_limits:
                state.component_diagnostic_limits[component] = RateLimitedLogger(
                    60, _last_warning_monotonic=now_monotonic - 60
                )
            limiter = state.component_diagnostic_limits[component]
            emit, suppressed = limiter.should_emit(now=now_monotonic)
            if emit:
                reports.append((component, probe_failure, suppressed))
        result = _accepted_response(state, components, current_components=accepted)
    for component, probe_failure, suppressed in reports:
        log_handled_exception(
            logger,
            probe_failure,
            message="Optional hardware observation unavailable.",
            operation=OPERATION_HARDWARE_COMPONENT_OBSERVATION,
            details={
                "component": component,
                "sequence": sequences[component],
                "suppressed_count": suppressed,
            },
            level="debug",
        )
    return result


def _accepted_response(
    state: HardwareManagerState,
    components: Sequence[str] | None,
    *,
    current_components: set[str] | None = None,
) -> JSONDict:
    if components:
        result = deepcopy(
            build_cached_response(last_full_info=state.last_full_info, components=components)
        )
    else:
        result = deepcopy(state.last_full_info)
    current = set(current_components or ())
    if "cpus" in current:
        current.add("cpu")
    for component, metadata in component_statuses(result).items():
        if isinstance(metadata, dict) and component not in current:
            metadata["sampled_current"] = False
    disk = result.get("disk")
    if isinstance(disk, list):
        for row in disk:
            status = row.get("observation_status") if isinstance(row, dict) else None
            if isinstance(status, dict) and "disk" not in current:
                status["sampled_current"] = False
    return result


def _derived_status(
    snapshot: JSONDict, dependencies: tuple[str, ...], checked_at_ms: int
) -> JSONDict:
    statuses = component_statuses(snapshot)
    observed_times: list[int] = []
    retained_times: list[int] = []
    complete = True
    sampled_current = True
    for component in dependencies:
        status = statuses.get(component)
        if component not in snapshot or (
            isinstance(status, dict) and status.get("status") not in ("available", "partial")
        ):
            complete = False
            sampled_current = False
            timestamp = status.get("observed_at_ms") if isinstance(status, dict) else None
            if component in snapshot and isinstance(timestamp, int):
                retained_times.append(timestamp)
            continue
        if isinstance(status, dict) and not is_current_observation_sample(status, checked_at_ms):
            sampled_current = False
        timestamp = status.get("observed_at_ms") if isinstance(status, dict) else checked_at_ms
        if isinstance(timestamp, int):
            observed_times.append(timestamp)
        if isinstance(status, dict) and status.get("status") == "partial":
            complete = False
    if not observed_times:
        return unavailable_status(checked_at_ms, error_code="monitoring_dependency_unavailable")
    result = observed_status(checked_at_ms, status="available" if complete else "partial")
    result["observed_at_ms"] = min(observed_times + retained_times)
    result["sampled_current"] = sampled_current
    return result
