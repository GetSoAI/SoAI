"""SoAI - Hardware manager settings resolution and factory [backend/hardware/manager/settings_factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import psutil

from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.validation.booleans import parse_bool
from hardware.info_gpu import log_gpu_tool_warnings
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.manager.dependencies import HardwareManagerSettings
from hardware.manager.history_config import initialize_history_config

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resolve_hardware_manager_settings",)

DEFAULT_GPU_INFO_CACHE_TTL_SECONDS = 1.0
DEFAULT_GPU_VENDOR_CACHE_TTL_SECONDS = 60.0
DEFAULT_NETWORK_SPEED_CACHE_TTL_SECONDS = 5.0


def _compute_hardware_manager_settings(
    config_dict: JSONDict,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
) -> HardwareManagerSettings:
    enabled = parse_bool(config_dict.get("ENABLED", True), default=True)
    monitoring_interval_ms = coerce_positive_int(
        config_dict.get("MONITORING_INTERVAL_MS", 3000),
        default=3000,
    )
    cache_ttl = coerce_positive_float(
        config_dict.get("HARDWARE_CACHE_TTL", 2),
        default=2,
        minimum=0.1,
    )
    detailed_gpu_info = parse_bool(config_dict.get("DETAILED_GPU_INFO", True), default=True)
    gpu_info_ttl = coerce_positive_float(
        config_dict.get("GPU_INFO_CACHE_TTL_SEC", DEFAULT_GPU_INFO_CACHE_TTL_SECONDS),
        default=DEFAULT_GPU_INFO_CACHE_TTL_SECONDS,
        minimum=0.1,
    )
    network_speed_ttl = coerce_positive_float(
        config_dict.get("NETWORK_SPEED_CACHE_TTL_SEC", DEFAULT_NETWORK_SPEED_CACHE_TTL_SECONDS),
        default=DEFAULT_NETWORK_SPEED_CACHE_TTL_SECONDS,
        minimum=0.1,
    )
    gpu_vendor_ttl = coerce_positive_float(
        config_dict.get("GPU_VENDOR_CACHE_TTL_SEC", DEFAULT_GPU_VENDOR_CACHE_TTL_SECONDS),
        default=DEFAULT_GPU_VENDOR_CACHE_TTL_SECONDS,
        minimum=0.1,
    )
    gpu_info_cache_service.set_cache_ttl(gpu_info_ttl)
    gpu_vendor_detection_service.set_cache_ttl(gpu_vendor_ttl)
    min_specs_enabled = parse_bool(
        config_dict.get("MINIMUM_SPECS_WARNING_ENABLED", True),
        default=True,
    )
    psutil.cpu_percent(interval=None)
    history_config = initialize_history_config(
        config_dict=config_dict,
        monitoring_interval_ms=int(monitoring_interval_ms),
    )
    log_gpu_tool_warnings(gpu_vendor_detection_service)
    gpu_info_cache_service.invalidate_cache()
    gpu_vendor_detection_service.invalidate_cache()
    return HardwareManagerSettings(
        enabled=bool(enabled),
        monitoring_interval_ms=int(monitoring_interval_ms),
        cache_ttl=cache_ttl,
        detailed_gpu_info=bool(detailed_gpu_info),
        min_specs_enabled=bool(min_specs_enabled),
        network_speed_cache_ttl_seconds=network_speed_ttl,
        history_config=history_config,
    )


def resolve_hardware_manager_settings(
    *,
    config_dict: JSONDict,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
) -> HardwareManagerSettings:
    config_payload = dict(config_dict)
    return _compute_hardware_manager_settings(
        config_dict=config_payload,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
    )
