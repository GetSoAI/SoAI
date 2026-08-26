"""SoAI - System-level host information [backend/hardware/info_system.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import platform
from typing import TYPE_CHECKING

import psutil

from core.timing.epoch import epoch_seconds_float
from hardware.windows_cpu_info import sanitize_cpu_display_name

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_os_info",
    "get_uptime_info",
)


def get_os_info() -> JSONDict:
    return {
        "system": platform.system(),
        "node_name": platform.node(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": sanitize_cpu_display_name(platform.processor()) or "",
    }


def get_uptime_info() -> JSONDict:
    boot_time_sec = float(psutil.boot_time())
    boot_time_ms = int(boot_time_sec * 1000)
    uptime_ms = int(max(0.0, epoch_seconds_float() - boot_time_sec) * 1000)
    return {
        "uptime_ms": uptime_ms,
        "boot_time_ms": boot_time_ms,
    }
