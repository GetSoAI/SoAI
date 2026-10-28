"""SoAI - GPU live sensor observation fields [backend/core/hardware/gpu_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("GPU_LIVE_SENSOR_FIELDS",)

GPU_LIVE_SENSOR_FIELDS = (
    "temperature",
    "temperature_hotspot_celsius",
    "utilization",
    "power_draw_watts",
    "core_clock_mhz",
    "mem_clock_mhz",
    "fan_speed",
    "fan_speed_rpm",
    "requested_core_clock_mhz",
    "configured_minimum_core_clock_mhz",
    "configured_maximum_core_clock_mhz",
)
