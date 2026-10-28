"""SoAI - System hardware capability detection for CPU and GPU [backend/hardware/manager/system_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import platform
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.public_projection import project_public_error
from core.hardware.gpu_inventory_errors import GPUObservationUnavailableError
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.hardware.vulkan_physical_acquisition import load_vulkan_library
from core.history.config_view import build_history_config_view
from core.logging.protocols import TraceLogger
from core.runtime.platform import (
    RuntimePlatform,
    get_runtime_platform,
    normalize_arch_id,
    normalize_os_id,
)
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from core.validation.numbers import coerce_float_from_json
from hardware.cpu_inventory.topology_totals import total_cpu_count
from hardware.cpu_rapl import RaplEnergyCache
from hardware.gpu_info_resolution import get_gpu_observation_for_services
from hardware.gpu_inventory.physical_observations import require_gpu_discovery_available
from hardware.info_cpu import get_cpu_info
from hardware.info_memory import get_memory_info
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.manager.cpu_feature_detection import detect_cpu_instruction_features
from hardware.manager.gpu_primary_selection import select_primary_gpu
from hardware.manager.system_info_cache import build_summary
from hardware.vendors.amd.adl_session import AdlRuntime
from hardware.vendors.vendor_metadata import gpu_feature_names_from_compute_drivers

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "SystemCapabilityEnvironment",
    "build_sampled_system_capabilities",
    "read_system_capability_environment",
    "sync_get_system_capabilities",
)

OPERATION_HARDWARE_SYSTEM_CAPABILITIES_VULKAN = "hardware.system_capabilities.vulkan"


@dataclass(frozen=True, slots=True)
class SystemCapabilityEnvironment:
    capabilities: JSONDict
    vulkan_available: bool


def sync_get_system_capabilities(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    monitoring_interval_ms: int,
    history_config: Mapping[str, JSONValue],
    history_enabled: bool,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    rapl_energy_cache: RaplEnergyCache,
    gpu_info: JSONDict | None = None,
    sampled_snapshot: Mapping[str, JSONValue] | None = None,
    adl_runtime: AdlRuntime | None = None,
) -> JSONDict:
    gpu_discovery: JSONDict | None = None
    snapshot: JSONDict = (
        dict(sampled_snapshot)
        if sampled_snapshot is not None
        else {
            "memory": get_memory_info(),
            "cpus": get_cpu_info(executor, rapl_energy_cache=rapl_energy_cache),
        }
    )
    try:
        if sampled_snapshot is not None:
            gpu_payload = sampled_snapshot.get("gpu")
        elif gpu_info is not None:
            gpu_payload = gpu_info
        else:
            observation = get_gpu_observation_for_services(
                executor,
                detailed=False,
                gpu_info_cache_service=gpu_info_cache_service,
                gpu_vendor_detection_service=gpu_vendor_detection_service,
                nvidia_nvml_gate=nvidia_nvml_gate,
                nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
                adl_runtime=adl_runtime,
            )
            if observation.refresh_failed or not observation.coverage_complete:
                require_gpu_discovery_available(observation.payload)
                if observation.refresh_error is not None:
                    raise observation.refresh_error
                raise GPUObservationUnavailableError(
                    "Complete current GPU observation is unavailable for discovery."
                )
            gpu_payload = observation.payload
        if isinstance(gpu_payload, dict):
            require_gpu_discovery_available(gpu_payload)
            snapshot["gpu"] = gpu_payload
    except SoAIError as error:
        if error.code not in (
            "gpu_inventory_timeout",
            "gpu_inventory_query_failed",
            "gpu_inventory_busy",
            "gpu_observation_unavailable",
        ):
            raise
        snapshot.pop("gpu", None)
        gpu_discovery = {"status": "unavailable", "error": project_public_error(error).to_dict()}
    environment = read_system_capability_environment(
        executor=executor,
        logger=logger,
        monitoring_interval_ms=monitoring_interval_ms,
        history_config=history_config,
        history_enabled=history_enabled,
    )
    capabilities = build_sampled_system_capabilities(environment, snapshot)
    if gpu_discovery is not None:
        capabilities["gpu_discovery"] = gpu_discovery
    return capabilities


def read_system_capability_environment(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    monitoring_interval_ms: int,
    history_config: Mapping[str, JSONValue],
    history_enabled: bool,
) -> SystemCapabilityEnvironment:
    runtime_platform = get_runtime_platform()
    caps: JSONDict = {
        "platform": _runtime_platform_os_id(runtime_platform),
        "arch": _runtime_platform_arch_id(runtime_platform),
        "platform_id": _runtime_platform_id(runtime_platform),
    }
    cpu_instruction_features = detect_cpu_instruction_features(
        executor,
        runtime_platform=runtime_platform,
        logger=logger,
    )
    cpu_features_set = {platform.machine().lower(), *cpu_instruction_features.features}
    caps["cpu_features"] = sorted(cpu_features_set)
    caps["cpu_features_observation"] = cpu_instruction_features.observation
    history_view = build_history_config_view(
        history_config,
        enabled_default=history_enabled,
        logging_interval_default=0,
        max_points_default=0,
        retention_hours_default=0,
        supported_intervals_default=(),
        supported_aggregations_default=(),
        logging_interval_minimum=0,
        max_points_minimum=0,
        default_interval_default=0,
        include_logging_interval_in_supported_intervals=False,
        allow_empty_intervals=True,
    )
    retention_hours = history_view.retention_hours
    caps["monitoring_interval_ms"] = int(monitoring_interval_ms)
    caps["history_retention_hours"] = retention_hours
    history_components = ["cpu", "gpu", "disk", "network"]
    history_payload: JSONDict = {
        "enabled": history_enabled,
        "retention_hours": retention_hours,
        "max_points": history_view.max_points,
        "logging_interval_ms": history_view.logging_interval_ms,
        "supported_intervals_ms": list(history_view.supported_intervals_ms),
        "default_interval_ms": history_view.default_interval_ms,
        "supported_aggregations": list(history_view.supported_aggregations),
        "components": history_components,
    }
    caps["history_config"] = history_payload
    vulkan_available = False
    try:
        load_vulkan_library()
        vulkan_available = True
    except (OSError, TypeError) as exception:
        log_handled_exception(
            logger,
            exception,
            message="Vulkan loader is unavailable.",
            operation=OPERATION_HARDWARE_SYSTEM_CAPABILITIES_VULKAN,
            level="trace",
        )
    return SystemCapabilityEnvironment(caps, vulkan_available)


def build_sampled_system_capabilities(
    environment: SystemCapabilityEnvironment,
    sampled_snapshot: Mapping[str, JSONValue],
) -> JSONDict:
    caps = dict(environment.capabilities)
    cpu_sample = sampled_snapshot.get("cpus")
    if isinstance(cpu_sample, list):
        cpu_info_list = [item for item in cpu_sample if isinstance(item, dict)]
        caps["cpu_physical_cores"] = total_cpu_count(cpu_info_list, "physical_cores")
        caps["cpu_logical_cores"] = total_cpu_count(cpu_info_list, "logical_cores")
    sampled_summary = build_summary(base_snapshot=sampled_snapshot)
    if "total_system_ram_gb" in sampled_summary:
        caps["system_ram_gb"] = coerce_float_from_json(
            sampled_summary["total_system_ram_gb"], default=0.0, allow_bool=True
        )
    if "total_system_memory_gb" in sampled_summary:
        caps["total_system_memory_gb"] = sampled_summary["total_system_memory_gb"]
    gpu_sample = sampled_snapshot.get("gpu")
    if isinstance(gpu_sample, dict):
        compute_drivers_value = gpu_sample.get("compute_drivers")
        compute_drivers = compute_drivers_value if isinstance(compute_drivers_value, dict) else {}
        caps["compute_drivers"] = compute_drivers
        gpu_features = gpu_feature_names_from_compute_drivers(compute_drivers)
        gpus_value = gpu_sample.get("gpus")
        if isinstance(gpus_value, list) and any(
            isinstance(gpu, dict)
            and gpu.get("vulkan_supported") is True
            and gpu.get("vulkan_enumeration_state") == "observed"
            for gpu in gpus_value
        ):
            gpu_features.add("vulkan")
        caps["gpu_features"] = sorted(gpu_features)
        primary_gpu = select_primary_gpu(gpu_sample, compute_drivers)
        primary_payload: JSONDict = {"vendor": primary_gpu.vendor, "name": primary_gpu.name}
        if "total_vram_gb" in sampled_summary:
            caps["total_vram_gb"] = sampled_summary["total_vram_gb"]
            primary_payload["vram_gb"] = primary_gpu.vram_gb
        caps["gpu"] = primary_payload
    return caps


def _runtime_platform_os_id(runtime_platform: RuntimePlatform) -> str:
    if runtime_platform.is_linux:
        return "linux"
    if runtime_platform.is_windows:
        return "windows"
    if runtime_platform.is_macos:
        return "darwin"
    return normalize_os_id(runtime_platform.os_name) or runtime_platform.os_name


def _runtime_platform_arch_id(runtime_platform: RuntimePlatform) -> str:
    try:
        raw_architecture = runtime_platform.architecture
    except AttributeError:
        raw_architecture = platform.machine().strip().lower()
    return normalize_arch_id(raw_architecture) or raw_architecture


def _runtime_platform_id(runtime_platform: RuntimePlatform) -> str:
    os_id = _runtime_platform_os_id(runtime_platform)
    architecture_id = _runtime_platform_arch_id(runtime_platform)
    return f"{os_id}-{architecture_id}" if os_id and architecture_id else ""
