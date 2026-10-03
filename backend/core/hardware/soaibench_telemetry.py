"""SoAI - Shared SoAIBench public telemetry policy [backend/core/hardware/soaibench_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict

__all__ = (
    "SOAIBENCH_PUBLIC_TELEMETRY_FIELDS",
    "project_public_telemetry",
    "telemetry_availability_is_consistent",
)

SOAIBENCH_PUBLIC_TELEMETRY_FIELDS = (
    "telemetry_available",
    "throttle_detected",
    "unavailable_sensors",
    "temperature_celsius",
    "max_temperature_celsius",
    "power_draw_watts",
    "avg_power_watts",
    "max_power_watts",
    "core_utilization_percent",
)


def project_public_telemetry(telemetry: JSONDict) -> JSONDict:
    return {field: telemetry.get(field) for field in SOAIBENCH_PUBLIC_TELEMETRY_FIELDS}


def telemetry_availability_is_consistent(telemetry: JSONDict) -> bool:
    available = telemetry.get("telemetry_available")
    throttle = telemetry.get("throttle_detected")
    unavailable = telemetry.get("unavailable_sensors")
    if not isinstance(available, bool) or (throttle is not None and not isinstance(throttle, bool)):
        return False
    if not isinstance(unavailable, list) or any(
        not isinstance(sensor, str) for sensor in unavailable
    ):
        return False
    temperature_available = any(
        telemetry.get(field) is not None
        for field in ("temperature_celsius", "max_temperature_celsius")
    )
    power_available = any(
        telemetry.get(field) is not None
        for field in ("power_draw_watts", "avg_power_watts", "max_power_watts")
    )
    expected_unavailable = [
        sensor
        for sensor, observed in (("temperature", temperature_available), ("power", power_available))
        if not observed
    ]
    expected_available = (
        temperature_available
        or power_available
        or telemetry.get("core_utilization_percent") is not None
    )
    return unavailable == expected_unavailable and available is expected_available
