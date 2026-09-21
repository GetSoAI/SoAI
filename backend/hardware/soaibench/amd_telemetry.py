"""SoAI - SoAIBench AMD fast sysfs telemetry reader [backend/hardware/soaibench/amd_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.filesystem.open_files import open_text
from core.types.json import JSONDict
from core.validation.numbers import coerce_float_from_json
from hardware.gpu_inventory.identity import normalize_pci_bdf

__all__ = ("read_amd_fast_telemetry",)

AMD_DEVICE_PREFIX = "gpu:amd-pci-"
DRM_SYSFS_ROOT = "/sys/class/drm"


def read_amd_fast_telemetry(device_id: str) -> JSONDict | None:
    pci_bdf = _device_id_pci_bdf(device_id)
    if pci_bdf is None:
        return None
    try:
        device_path = _find_drm_device_path(pci_bdf)
        if device_path is None:
            return None
        return _read_device_telemetry(device_path)
    except (FileNotFoundError, PermissionError):
        return None


def _device_id_pci_bdf(device_id: str) -> str | None:
    if not device_id.startswith(AMD_DEVICE_PREFIX):
        return None
    pci_bdf = normalize_pci_bdf(device_id.removeprefix(AMD_DEVICE_PREFIX))
    return pci_bdf or None


def _find_drm_device_path(pci_bdf: str) -> str | None:
    for entry_name in os.listdir(DRM_SYSFS_ROOT):
        if not _is_drm_card_node(entry_name):
            continue
        device_path = os.path.join(DRM_SYSFS_ROOT, entry_name, "device")
        if not os.path.isdir(device_path):
            continue
        resolved_bdf = normalize_pci_bdf(os.path.basename(os.path.realpath(device_path)))
        if resolved_bdf == pci_bdf:
            return device_path
    return None


def _is_drm_card_node(entry_name: str) -> bool:
    suffix = entry_name.removeprefix("card")
    return bool(suffix) and suffix.isdigit()


def _read_device_telemetry(device_path: str) -> JSONDict:
    telemetry: JSONDict = {}
    utilization = _read_float_file(os.path.join(device_path, "gpu_busy_percent"))
    temperature = _read_hwmon_scaled(device_path, "temp1_input", divisor=1000.0)
    power = _read_hwmon_scaled(device_path, "power1_average", divisor=1_000_000.0)
    if power is None:
        power = _read_hwmon_scaled(device_path, "power1_input", divisor=1_000_000.0)
    if utilization is not None:
        telemetry["core_utilization_percent"] = utilization
    if temperature is not None:
        telemetry["temperature_celsius"] = temperature
    if power is not None:
        telemetry["avg_power_watts"] = power
        telemetry["max_power_watts"] = power
        telemetry["power_draw_watts"] = power
    return telemetry


def _read_hwmon_scaled(device_path: str, filename: str, *, divisor: float) -> float | None:
    hwmon_root = os.path.join(device_path, "hwmon")
    if not os.path.isdir(hwmon_root):
        return None
    for entry_name in os.listdir(hwmon_root):
        candidate = os.path.join(hwmon_root, entry_name, filename)
        value = _read_float_file(candidate)
        if value is not None:
            return value / divisor
    return None


def _read_float_file(path: str) -> float | None:
    if not os.path.isfile(path):
        return None
    with open_text(path, encoding="utf-8", errors="replace") as handle:
        return coerce_float_from_json(
            handle.read().strip(),
            default=None,
            allow_bool=False,
            allow_nonfinite=False,
        )
