"""SoAI - System hardware capability detection for CPU and GPU [backend/hardware/manager/system_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import platform
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.history.config_view import build_history_config_view
from core.logging.protocols import TraceLogger
from core.runtime.platform import (
    RuntimePlatform,
    get_runtime_platform,
    normalize_arch_id,
    normalize_os_id,
)
from core.system.protocols import CommandExecutorProtocol
from core.validation.numbers import (
    coerce_float_from_json,
    coerce_int_from_json,
)
from hardware.cpu_rapl import RaplEnergyCache
from hardware.gpu_info_resolution import (
    build_gpu_info_service_dependencies,
    resolve_gpu_info_for_services,
)
from hardware.info_cpu import get_cpu_info
from hardware.info_memory import get_memory_info
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.manager.cpu_feature_detection import detect_cpu_instruction_features
from hardware.manager.gpu_primary_selection import select_primary_gpu
from hardware.operations import sum_vram_gb
from hardware.vendors.vendor_metadata import gpu_feature_names_from_compute_drivers

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("sync_get_system_capabilities",)

OPERATION_HARDWARE_SYSTEM_CAPABILITIES_VULKAN = "hardware.system_capabilities.vulkan"


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
) -> JSONDict:
    runtime_platform = get_runtime_platform()

    caps: JSONDict = {
        "platform": _runtime_platform_os_id(runtime_platform),
        "arch": _runtime_platform_arch_id(runtime_platform),
        "platform_id": _runtime_platform_id(runtime_platform),
        "cpu_features": [],
        "gpu_features": [],
        "gpu": {"vendor": "none", "vram_gb": 0, "name": "N/A"},
        "compute_drivers": {},
    }
    mem_info = get_memory_info()
    cpu_info_list = [
        item
        for item in get_cpu_info(executor, rapl_energy_cache=rapl_energy_cache)
        if isinstance(item, dict)
    ]
    total_physical_cores = sum(
        coerce_int_from_json(cpu.get("physical_cores", 0), default=0, allow_bool=True) or 0
        for cpu in cpu_info_list
    )
    total_logical_cores = sum(
        coerce_int_from_json(cpu.get("logical_cores", 0), default=0, allow_bool=True) or 0
        for cpu in cpu_info_list
    )
    system_ram_gb = coerce_float_from_json(
        mem_info.get("total_gb", 0),
        default=0.0,
        allow_bool=True,
    )
    if system_ram_gb is None:
        system_ram_gb = 0.0
    caps.update(
        {
            "system_ram_gb": system_ram_gb,
            "cpu_physical_cores": total_physical_cores,
            "cpu_logical_cores": total_logical_cores,
        },
    )
    cpu_features_set = {platform.machine().lower()}
    cpu_features_set.update(
        detect_cpu_instruction_features(
            executor,
            runtime_platform=runtime_platform,
            logger=logger,
        ),
    )
    caps["cpu_features"] = sorted(list(cpu_features_set))
    gpu_info_services = build_gpu_info_service_dependencies(
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
    )
    full_gpu_info = resolve_gpu_info_for_services(
        executor,
        deps=gpu_info_services,
        gpu_info=gpu_info,
    )
    total_vram_gb = float(sum_vram_gb(full_gpu_info))
    gpus_value = full_gpu_info.get("gpus")
    gpus_present = isinstance(gpus_value, list) and any(isinstance(gpu, dict) for gpu in gpus_value)
    caps["total_vram_gb"] = total_vram_gb
    caps["total_system_memory_gb"] = round(system_ram_gb + total_vram_gb, 2)
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
    gpu_features_set: set[str] = set()
    compute_drivers_value = full_gpu_info.get("compute_drivers")
    compute_drivers = compute_drivers_value if isinstance(compute_drivers_value, dict) else {}
    if compute_drivers:
        caps["compute_drivers"] = compute_drivers
        gpu_features_set.update(gpu_feature_names_from_compute_drivers(compute_drivers))
    primary_gpu = select_primary_gpu(full_gpu_info, compute_drivers)
    caps["gpu"] = {
        "vendor": primary_gpu.vendor,
        "vram_gb": primary_gpu.vram_gb,
        "name": primary_gpu.name,
    }
    vulkan_lib_name = {
        "Linux": "libvulkan.so.1",
        "Windows": "vulkan-1.dll",
        "Darwin": "libvulkan.1.dylib",
    }.get(platform.system())
    if gpus_present and vulkan_lib_name:
        try:
            loader_cls = ctypes.CDLL
            loader_cls(vulkan_lib_name)
            gpu_features_set.add("vulkan")
        except (OSError, TypeError) as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to load Vulkan library.",
                operation=OPERATION_HARDWARE_SYSTEM_CAPABILITIES_VULKAN,
                details={"library": vulkan_lib_name},
                level="trace",
            )
    caps["gpu_features"] = sorted(list(gpu_features_set))
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
