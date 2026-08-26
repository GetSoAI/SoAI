"""SoAI - Core hardware constants [backend/core/hardware/constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

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
