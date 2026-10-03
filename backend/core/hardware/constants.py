"""SoAI - Core hardware constants [backend/core/hardware/constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

HARDWARE_HISTORY_COMPONENTS = ("cpu", "gpu", "disk", "network")

NETWORK_INTERFACE_STAT_KEYS: tuple[str, ...] = (
    "bytes_sent",
    "bytes_recv",
    "packets_sent",
    "packets_recv",
    "errin",
    "errout",
    "dropin",
    "dropout",
)
NETWORK_INTERFACE_STAT_KEYS_WITH_SPEED: tuple[str, ...] = (
    *NETWORK_INTERFACE_STAT_KEYS,
    "upload_mbps",
    "download_mbps",
)
GPU_METRIC_COLUMNS: tuple[str, ...] = (
    "utilization",
    "percent_used",
    "temperature",
    "power_draw_watts",
    "power_limit_watts",
    "core_clock_mhz",
    "mem_clock_mhz",
)
CPU_METRIC_COLUMNS: tuple[str, ...] = (
    "usage_percent",
    "temperature_celsius",
    "power_draw_watts",
    "memory_percent",
    "power_limit_watts",
)
DISK_METRIC_COLUMNS: tuple[str, ...] = (
    "total_bytes",
    "used_bytes",
    "free_bytes",
    "percent_used",
)


def get_hardware_history_metric_columns(component: str) -> tuple[str, ...]:
    match component:
        case "cpu":
            return CPU_METRIC_COLUMNS
        case "gpu":
            return GPU_METRIC_COLUMNS
        case "disk":
            return DISK_METRIC_COLUMNS
        case "network":
            return NETWORK_INTERFACE_STAT_KEYS_WITH_SPEED
        case _:
            return ()
