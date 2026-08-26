"""SoAI - Disk usage reading with parent fallback [backend/core/hardware/disk_usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from core.validation.integers import coerce_non_negative_int_or_zero
from core.validation.numbers import coerce_int_from_json

__all__ = (
    "DiskUsageSnapshot",
    "read_disk_usage_with_parent_fallback",
)


@dataclass(frozen=True, slots=True)
class DiskUsageSnapshot:
    check_path: str
    disk_usage_path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int


def _read_disk_usage_values(path: str) -> tuple[str, int, int, int]:
    usage_path = path
    while True:
        try:
            usage = shutil.disk_usage(usage_path)
            return usage_path, usage.total, usage.used, usage.free
        except FileNotFoundError:
            parent = os.path.dirname(usage_path)
            if not parent or parent == usage_path:
                raise
            usage_path = parent


def read_disk_usage_with_parent_fallback(path: str) -> DiskUsageSnapshot:
    check_path = os.path.abspath(path)
    usage_path, total_value, used_value, free_value = _read_disk_usage_values(check_path)
    return DiskUsageSnapshot(
        check_path=check_path,
        disk_usage_path=usage_path,
        total_bytes=coerce_non_negative_int_or_zero(coerce_int_from_json(total_value, default=0)),
        used_bytes=coerce_non_negative_int_or_zero(coerce_int_from_json(used_value, default=0)),
        free_bytes=coerce_non_negative_int_or_zero(coerce_int_from_json(free_value, default=0)),
    )
