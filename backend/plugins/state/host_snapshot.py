"""SoAI - Plugin compatibility host capability collection [backend/plugins/state/host_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import platform
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.protocols import GetGpuInfoCallable
from core.logging.trace import get_logger
from core.runtime.platform import (
    normalize_arch_id,
    normalize_os_id,
    normalize_platform_id,
)
from core.types.json import is_json_dict, is_json_value
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.capability_normalization import as_json_list

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("get_host_capability_snapshot",)

LOGGER_NAME = "SoAI.plugins.state.host_snapshot"
OPERATION = "plugin_state.get_host_capability_snapshot"


def _extract_gpu_vendors(gpu_info: JSONValue) -> list[str]:
    vendors: list[str] = []
    if isinstance(gpu_info, dict):
        entries_value = gpu_info.get("gpus")
        entries = entries_value if isinstance(entries_value, list) else []
        for entry in entries:
            if isinstance(entry, dict):
                vendor = str(entry.get("type", "")).strip().lower()
                if vendor:
                    vendors.append(vendor)
    return list(dict.fromkeys(vendors))


def _build_gpu_summary(vendors: list[str]) -> JSONDict:
    return {
        "available": bool(vendors),
        "vendors": as_json_list(vendors),
        "features": [],
        "primary_vendor": None,
        "total_vram_gb": None,
        "drivers": {},
        "inventory_available": False,
    }


def _enrich_gpu_summary_from_system_caps(
    gpu_summary: JSONDict,
    vendors: list[str],
    system_caps: JSONDict,
) -> tuple[str, str, str, str, str, JSONDict]:
    gpu_summary["inventory_available"] = True
    gpu_meta_value = system_caps.get("gpu")
    gpu_meta = gpu_meta_value if is_json_dict(gpu_meta_value) else {}
    primary_vendor = str(gpu_meta.get("vendor", "")).strip().lower() if gpu_meta else ""
    if primary_vendor:
        gpu_summary["primary_vendor"] = primary_vendor
        if primary_vendor not in vendors:
            vendors.append(primary_vendor)
            gpu_summary["vendors"] = as_json_list(vendors)
            gpu_summary["available"] = True
    features_value = system_caps.get("gpu_features")
    features = features_value if isinstance(features_value, list) else []
    gpu_summary["features"] = as_json_list(
        list(
            dict.fromkeys(
                str(feature).strip().lower() for feature in features if str(feature).strip()
            ),
        ),
    )
    drivers_value = system_caps.get("compute_drivers")
    driver_dict = drivers_value if is_json_dict(drivers_value) else {}
    gpu_summary["drivers"] = driver_dict
    driver_details = {
        driver_name.strip().lower(): driver_info
        for driver_name, driver_info in driver_dict.items()
        if isinstance(driver_name, str) and driver_name.strip()
    }
    total_vram = system_caps.get("total_vram_gb")
    if isinstance(total_vram, int | float):
        gpu_summary["total_vram_gb"] = float(total_vram)
    platform_id_value = system_caps.get("platform_id")
    raw_platform_id = (
        str(platform_id_value).strip().lower() if isinstance(platform_id_value, str) else ""
    )
    platform_id = normalize_platform_id(raw_platform_id) or ""
    raw_os_name = str(system_caps.get("platform") or "").strip().lower()
    raw_arch_name = str(system_caps.get("arch") or "").strip().lower()
    os_name = normalize_os_id(raw_os_name) or raw_os_name
    arch_name = normalize_arch_id(raw_arch_name) or raw_arch_name
    driver_details_json: JSONDict = {}
    for name, value in driver_details.items():
        if is_json_value(value):
            driver_details_json[name] = value
        else:
            driver_details_json[name] = str(value)
    if not platform_id and os_name and arch_name:
        platform_id = f"{os_name}-{arch_name}"
    return os_name, arch_name, platform_id, raw_os_name, raw_arch_name, driver_details_json


def _extract_driver_names(
    gpu_summary: JSONDict,
) -> tuple[list[JSONValue], list[JSONValue]]:
    driver_map_value = gpu_summary.get("drivers")
    driver_map = driver_map_value if isinstance(driver_map_value, dict) else {}
    driver_names_raw = [
        driver_name.strip()
        for driver_name in driver_map
        if isinstance(driver_name, str) and driver_name.strip()
    ]
    normalized_driver_names_raw = list(
        dict.fromkeys(driver_name.lower() for driver_name in driver_names_raw),
    )
    return as_json_list(driver_names_raw), as_json_list(normalized_driver_names_raw)


async def get_host_capability_snapshot(
    manager: PluginManagerRuntimeProtocol | None,
    get_gpu_info: GetGpuInfoCallable,
    *,
    include_gpu_inventory: bool,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    system_caps: JSONDict | None = None
    if manager is not None:
        try:
            system_caps_value = (
                await manager.dependencies.infrastructure.hw_manager.get_system_capabilities()
            )
            system_caps = system_caps_value if is_json_dict(system_caps_value) else None
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to collect system capabilities",
                operation=OPERATION,
            )
    gpu_info: JSONDict = {}
    if include_gpu_inventory:
        try:
            gpu_info = await asyncio.to_thread(get_gpu_info, False)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to collect GPU inventory",
                operation=OPERATION,
            )
    vendors = _extract_gpu_vendors(gpu_info)
    gpu_summary = _build_gpu_summary(vendors)
    os_name: str = ""
    arch_name: str = ""
    platform_id: str = ""
    raw_os_name: str = ""
    raw_arch_name: str = ""
    driver_details_json: JSONDict = {}
    if system_caps is not None:
        (
            os_name,
            arch_name,
            platform_id,
            raw_os_name,
            raw_arch_name,
            driver_details_json,
        ) = _enrich_gpu_summary_from_system_caps(gpu_summary, vendors, system_caps)
    if not raw_os_name:
        raw_os_name = platform.system().strip().lower()
    if not raw_arch_name:
        raw_arch_name = platform.machine().strip().lower()
    os_name = normalize_os_id(raw_os_name) or raw_os_name
    arch_name = normalize_arch_id(raw_arch_name) or raw_arch_name
    if not platform_id and os_name and arch_name:
        platform_id = f"{os_name}-{arch_name}"
    driver_names, normalized_driver_names = _extract_driver_names(gpu_summary)
    snapshot: JSONDict = {}
    snapshot["os"] = os_name
    snapshot["arch"] = arch_name
    snapshot["platform"] = platform_id
    snapshot["raw_os"] = raw_os_name
    snapshot["raw_arch"] = raw_arch_name
    snapshot["gpu"] = gpu_summary
    snapshot["gpu_features"] = gpu_summary.get("features", [])
    snapshot["drivers"] = driver_names
    snapshot["normalized_drivers"] = normalized_driver_names
    snapshot["driver_details"] = driver_details_json
    return snapshot
