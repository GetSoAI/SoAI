"""SoAI - Physically bound AMD sysfs telemetry [backend/hardware/vendors/amd/sysfs_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_text
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from hardware.gpu_inventory.drm_physical_observations import parse_drm_uevent
from hardware.gpu_inventory.sysfs_metrics import read_hwmon_scaled, read_sysfs_metric
from hardware.vendors.amd.radeon_memory import read_radeon_memory_capacity
from hardware.vendors.amd.radeontop_telemetry import read_radeontop_telemetry

__all__ = ("read_amd_sysfs_telemetry", "read_radeon_control_facilities")
DRM_SYSFS_ROOT = "/sys/class/drm"


def read_amd_sysfs_telemetry(pci_bdf: str, executor: CommandExecutorProtocol) -> JSONDict | None:
    canonical = normalize_observed_full_pci_bdf(pci_bdf)
    if not canonical:
        raise ValidationError("AMD sysfs telemetry requires full physical PCI authority.")
    device_path = _find_drm_device_path(canonical)
    if device_path is None:
        return None
    telemetry = _read_device_telemetry(device_path)
    if os.path.basename(os.path.realpath(os.path.join(device_path, "driver"))) == "radeon":
        try:
            tool_metrics = read_radeontop_telemetry(DRM_SYSFS_ROOT, canonical, executor)
        except (OSError, StateError, ValidationError) as exception:
            telemetry["legacy_tool_unavailable_reason"] = (
                "permission_denied"
                if isinstance(exception, PermissionError)
                else "native_sensor_query_failed"
            )
        else:
            for field, value in tool_metrics.items():
                if field not in telemetry:
                    telemetry[field] = value
    if (
        "memory_total_bytes" not in telemetry
        and os.path.basename(os.path.realpath(os.path.join(device_path, "driver"))) == "radeon"
    ):
        try:
            capacity = read_radeon_memory_capacity(device_path, canonical)
        except (OSError, StateError, ValidationError) as exception:
            telemetry["memory_total_unavailable_reason"] = (
                "permission_denied"
                if isinstance(exception, PermissionError)
                else "native_memory_unavailable"
            )
        else:
            if capacity is not None:
                telemetry["memory_total_bytes"] = capacity
                telemetry["memory_total_source"] = "radeon.DRM_RADEON_GEM_INFO"
    if _find_drm_device_path(canonical) != device_path:
        raise ValidationError("AMD physical sysfs relation changed during observation.")
    return telemetry


def _find_drm_device_path(pci_bdf: str) -> str | None:
    candidates: set[str] = set()
    for entry_name in sorted(os.listdir(DRM_SYSFS_ROOT)):
        if not _is_drm_card_node(entry_name):
            continue
        device_path = os.path.join(DRM_SYSFS_ROOT, entry_name, "device")
        if not os.path.isdir(device_path):
            continue
        try:
            with open_text(os.path.join(device_path, "uevent"), encoding="utf-8") as handle:
                fields = parse_drm_uevent(handle.read(4096))
        except FileNotFoundError:
            continue
        observed = normalize_observed_full_pci_bdf(fields.get("PCI_SLOT_NAME", ""))
        if observed != pci_bdf:
            continue
        driver = fields.get("DRIVER")
        if (
            driver not in ("amdgpu", "radeon")
            or fields.get("PCI_ID", "").split(":")[0].lower() != "1002"
        ):
            raise ValidationError("AMD sysfs telemetry contradicts bound vendor or driver.")
        if os.path.basename(os.path.realpath(os.path.join(device_path, "driver"))) != driver:
            raise ValidationError("AMD sysfs telemetry has no verified driver binding.")
        candidates.add(os.path.realpath(device_path))
    if len(candidates) > 1:
        raise ValidationError("AMD sysfs telemetry physical relation is ambiguous.")
    return next(iter(candidates)) if candidates else None


def _is_drm_card_node(entry_name: str) -> bool:
    suffix = entry_name.removeprefix("card")
    return bool(suffix) and suffix.isdigit()


def _read_device_telemetry(device_path: str) -> JSONDict:
    telemetry: JSONDict = {}
    utilization = read_sysfs_metric(os.path.join(device_path, "gpu_busy_percent"))
    temperature = read_hwmon_scaled(device_path, "temp1_input", divisor=1000.0)
    power = read_hwmon_scaled(device_path, "power1_average", divisor=1_000_000.0)
    if power is None:
        power = read_hwmon_scaled(device_path, "power1_input", divisor=1_000_000.0)
    if utilization is not None and 0 <= utilization <= 100:
        telemetry["core_utilization_percent"] = utilization
    if temperature is not None:
        telemetry["temperature_celsius"] = temperature
    if power is not None:
        telemetry["avg_power_watts"] = power
        telemetry["max_power_watts"] = power
        telemetry["power_draw_watts"] = power
    capacity = read_sysfs_metric(os.path.join(device_path, "mem_info_vram_total"))
    if capacity is not None and capacity > 0 and capacity.is_integer():
        telemetry["memory_total_bytes"] = int(capacity)
    return telemetry


def read_radeon_control_facilities(pci_bdf: str) -> dict[str, bool]:
    canonical = normalize_observed_full_pci_bdf(pci_bdf)
    if not canonical:
        raise ValidationError("Radeon facilities require a full physical identity.")
    directory = _find_drm_device_path(canonical)
    if (
        directory is None
        or os.path.basename(os.path.realpath(os.path.join(directory, "driver"))) != "radeon"
    ):
        raise StateError("The physical radeon facility scope is unavailable.")
    files = set(os.listdir(directory))
    clock_controls = "pp_od_clk_voltage" in files
    facilities = dict.fromkeys(GPU_DIRECT_SETTING_FIELDS, False)
    facilities["core_clock"] = clock_controls
    facilities["mem_clock"] = clock_controls
    if "hwmon" in files:
        root = os.path.join(directory, "hwmon")
        for name in os.listdir(root):
            sensors = set(os.listdir(os.path.join(root, name)))
            facilities["power_limit"] = facilities["power_limit"] or "power1_cap" in sensors
            facilities["fan_speed"] = facilities["fan_speed"] or "pwm1" in sensors
    if _find_drm_device_path(canonical) != directory:
        raise ValidationError("Radeon facility identity changed during observation.")
    return facilities
