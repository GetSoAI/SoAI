"""SoAI - Optional DRM sysfs sensor values [backend/hardware/gpu_inventory/sysfs_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.filesystem.open_files import open_text
from core.validation.numbers import coerce_float_from_json

__all__ = ("read_hwmon_scaled", "read_sysfs_metric", "read_sysfs_text")


def read_hwmon_scaled(device_path: str, filename: str, *, divisor: float) -> float | None:
    hwmon_root = os.path.join(device_path, "hwmon")
    if not os.path.isdir(hwmon_root):
        return None
    for entry_name in os.listdir(hwmon_root):
        candidate = os.path.join(hwmon_root, entry_name, filename)
        value = read_sysfs_metric(candidate)
        if value is not None:
            return value / divisor
    return None


def read_sysfs_metric(path: str) -> float | None:
    text = read_sysfs_text(path)
    if text is None:
        return None
    return coerce_float_from_json(text, default=None, allow_bool=False, allow_nonfinite=False)


def read_sysfs_text(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    with open_text(path, encoding="utf-8", errors="replace") as handle:
        return handle.read(256).strip()
