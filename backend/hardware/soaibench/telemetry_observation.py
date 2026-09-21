"""SoAI - SoAIBench typed telemetry observations [backend/hardware/soaibench/telemetry_observation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.types.json import JSONDict

__all__ = ("SoAIBenchTelemetrySnapshot",)


@dataclass(frozen=True, slots=True)
class SoAIBenchTelemetrySnapshot:
    temperature_celsius: float | None
    power_watts: float | None
    utilization_percent: float | None
    throttle_detected: bool | None
    temperature_limit_celsius: float | None
    temperature_exceeded: bool
    instability_reason: str | None
    instability_message: str | None
    diagnostic_code: str | None

    @property
    def telemetry_available(self) -> bool:
        return any(
            value is not None
            for value in (
                self.temperature_celsius,
                self.power_watts,
                self.utilization_percent,
            )
        )

    @property
    def summary(self) -> JSONDict:
        unavailable_sensors: list[str] = []
        if self.temperature_celsius is None:
            unavailable_sensors.append("temperature")
        if self.power_watts is None:
            unavailable_sensors.append("power")
        summary: JSONDict = {
            "telemetry_available": self.telemetry_available,
            "telemetry_sample_count": 1,
            "temperature_sample_count": int(self.temperature_celsius is not None),
            "power_sample_count": int(self.power_watts is not None),
            "utilization_sample_count": int(self.utilization_percent is not None),
            "unavailable_sensors": unavailable_sensors,
            "throttle_detected": self.throttle_detected,
        }
        if self.temperature_celsius is not None:
            summary["temperature_celsius"] = self.temperature_celsius
            summary["max_temperature_celsius"] = self.temperature_celsius
        if self.power_watts is not None:
            summary["avg_power_watts"] = self.power_watts
            summary["max_power_watts"] = self.power_watts
            summary["power_draw_watts"] = self.power_watts
        if self.utilization_percent is not None:
            summary["core_utilization_percent"] = self.utilization_percent
        if self.temperature_limit_celsius is not None:
            summary["temperature_limit_celsius"] = self.temperature_limit_celsius
        if self.diagnostic_code is not None:
            summary["telemetry_warning"] = self.diagnostic_code
        return summary
