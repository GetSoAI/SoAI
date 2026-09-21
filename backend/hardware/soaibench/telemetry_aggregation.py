"""SoAI - SoAIBench telemetry aggregation [backend/hardware/soaibench/telemetry_aggregation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hardware.soaibench.telemetry_observation import SoAIBenchTelemetrySnapshot

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("SoAIBenchTelemetryAccumulator",)


@dataclass(slots=True)
class SoAIBenchTelemetryAccumulator:
    telemetry_sample_count: int = 0
    temperature_sample_count: int = 0
    power_sample_count: int = 0
    utilization_sample_count: int = 0
    power_sum_watts: float = 0.0
    latest_temperature_celsius: float | None = None
    latest_power_watts: float | None = None
    max_core_utilization_percent: float | None = None
    max_temperature_celsius: float | None = None
    max_power_watts: float | None = None
    throttle_detected: bool | None = None
    diagnostic_counts: dict[str, int] = field(default_factory=dict[str, int])

    def add(self, snapshot: SoAIBenchTelemetrySnapshot) -> None:
        self.telemetry_sample_count += 1
        if snapshot.temperature_celsius is not None:
            self.temperature_sample_count += 1
            self.latest_temperature_celsius = snapshot.temperature_celsius
            self.max_temperature_celsius = _max_value(
                self.max_temperature_celsius,
                snapshot.temperature_celsius,
            )
        if snapshot.power_watts is not None:
            self.power_sample_count += 1
            self.power_sum_watts += snapshot.power_watts
            self.latest_power_watts = snapshot.power_watts
            self.max_power_watts = _max_value(self.max_power_watts, snapshot.power_watts)
        if snapshot.utilization_percent is not None:
            self.utilization_sample_count += 1
            self.max_core_utilization_percent = _max_value(
                self.max_core_utilization_percent,
                snapshot.utilization_percent,
            )
        if snapshot.throttle_detected is True:
            self.throttle_detected = True
        elif snapshot.throttle_detected is False and self.throttle_detected is None:
            self.throttle_detected = False
        if snapshot.diagnostic_code is not None:
            self.diagnostic_counts[snapshot.diagnostic_code] = (
                self.diagnostic_counts.get(snapshot.diagnostic_code, 0) + 1
            )

    def summary(self) -> JSONDict:
        unavailable_sensors: list[str] = []
        if self.temperature_sample_count == 0:
            unavailable_sensors.append("temperature")
        if self.power_sample_count == 0:
            unavailable_sensors.append("power")
        summary: JSONDict = {
            "telemetry_available": any(
                count > 0
                for count in (
                    self.temperature_sample_count,
                    self.power_sample_count,
                    self.utilization_sample_count,
                )
            ),
            "telemetry_sample_count": self.telemetry_sample_count,
            "temperature_sample_count": self.temperature_sample_count,
            "power_sample_count": self.power_sample_count,
            "utilization_sample_count": self.utilization_sample_count,
            "unavailable_sensors": unavailable_sensors,
            "throttle_detected": self.throttle_detected,
        }
        if self.latest_temperature_celsius is not None:
            summary["temperature_celsius"] = self.latest_temperature_celsius
        if self.max_temperature_celsius is not None:
            summary["max_temperature_celsius"] = self.max_temperature_celsius
        if self.latest_power_watts is not None:
            summary["power_draw_watts"] = self.latest_power_watts
        if self.max_core_utilization_percent is not None:
            summary["core_utilization_percent"] = self.max_core_utilization_percent
        if self.power_sample_count > 0:
            summary["avg_power_watts"] = round(
                self.power_sum_watts / self.power_sample_count,
                3,
            )
        if self.max_power_watts is not None:
            summary["max_power_watts"] = self.max_power_watts
        if self.diagnostic_counts:
            summary["telemetry_diagnostic_counts"] = dict(sorted(self.diagnostic_counts.items()))
            summary["telemetry_warnings"] = sorted(self.diagnostic_counts)
        return summary


def _max_value(current: float | None, value: float) -> float:
    if current is None:
        return value
    return max(current, value)
