"""SoAI - SoAIBench GPU telemetry snapshots [backend/hardware/soaibench/telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.types.json import is_str_list
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.numbers import coerce_float_from_json
from hardware.control_snapshots import find_gpu_entry
from hardware.soaibench.amd_telemetry import read_amd_fast_telemetry
from hardware.soaibench.nvidia_telemetry import read_nvidia_fast_telemetry

if TYPE_CHECKING:
    from core.hardware.protocols import HardwareManagerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SoAIBenchTelemetryAccumulator",
    "SoAIBenchTelemetrySnapshot",
    "read_soaibench_telemetry_snapshot",
    "settings_snapshot_from_gpu",
)


@dataclass(frozen=True, slots=True)
class SoAIBenchTelemetrySnapshot:
    summary: JSONDict
    telemetry_available: bool
    temperature_available: bool
    power_available: bool
    temperature_exceeded: bool
    instability_reason: str | None
    instability_message: str | None


@dataclass(slots=True)
class SoAIBenchTelemetryAccumulator:
    power_sample_count: int = 0
    power_sum_watts: float = 0.0
    latest_temperature_celsius: float | None = None
    latest_power_watts: float | None = None
    max_core_utilization_percent: float | None = None
    max_temperature_celsius: float | None = None
    max_power_watts: float | None = None
    throttle_detected: bool = False
    unavailable_sensors: set[str] = field(default_factory=set[str])

    def add(self, snapshot: SoAIBenchTelemetrySnapshot) -> None:
        temperature = _numeric(snapshot.summary.get("temperature_celsius"))
        power = _numeric(snapshot.summary.get("avg_power_watts"))
        core_utilization = _numeric(snapshot.summary.get("core_utilization_percent"))
        if temperature is None:
            self.unavailable_sensors.add("temperature")
        else:
            self.latest_temperature_celsius = temperature
            self.max_temperature_celsius = _max_value(
                self.max_temperature_celsius,
                temperature,
            )
        if power is None:
            self.unavailable_sensors.add("power")
        else:
            self.power_sample_count += 1
            self.power_sum_watts += power
            self.latest_power_watts = power
            self.max_power_watts = _max_value(self.max_power_watts, power)
        if core_utilization is not None:
            self.max_core_utilization_percent = _max_value(
                self.max_core_utilization_percent,
                core_utilization,
            )
        self.throttle_detected = (
            self.throttle_detected or snapshot.summary.get("throttle_detected") is True
        )
        raw_unavailable = snapshot.summary.get("unavailable_sensors")
        if is_str_list(raw_unavailable):
            for sensor in raw_unavailable:
                self.unavailable_sensors.add(sensor)

    def summary(self) -> JSONDict:
        telemetry_available = not self.unavailable_sensors
        summary: JSONDict = {
            "telemetry_available": telemetry_available,
            "unavailable_sensors": sorted(self.unavailable_sensors),
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
            summary["avg_power_watts"] = round(self.power_sum_watts / self.power_sample_count, 3)
        if self.max_power_watts is not None:
            summary["max_power_watts"] = self.max_power_watts
        return summary


async def read_soaibench_telemetry_snapshot(
    hardware_manager: HardwareManagerProtocol,
    *,
    device_id: str,
    temperature_limit_celsius: float | None,
) -> SoAIBenchTelemetrySnapshot:
    fast_telemetry = read_nvidia_fast_telemetry(
        device_id,
        nvml_gate=hardware_manager.nvidia_nvml_gate,
    )
    if fast_telemetry is None:
        fast_telemetry = read_amd_fast_telemetry(device_id)
    if fast_telemetry is not None:
        return _snapshot_from_metrics(
            temperature=_numeric(fast_telemetry.get("temperature_celsius")),
            power=_numeric(fast_telemetry.get("avg_power_watts")),
            core_utilization=_numeric(fast_telemetry.get("core_utilization_percent")),
            temperature_limit_celsius=temperature_limit_celsius,
        )
    snapshot = await hardware_manager.get_system_info(["gpu"], cache=False)
    gpu = find_gpu_entry(snapshot, device_id)
    if gpu is None:
        return _snapshot(
            {
                "telemetry_available": False,
                "telemetry_warning": "gpu_telemetry_unavailable",
                "unavailable_sensors": ["temperature", "power"],
            },
        )
    return _snapshot_from_metrics(
        temperature=_numeric(gpu.get("temperature")),
        power=_numeric(gpu.get("power_draw_watts")),
        core_utilization=_numeric(gpu.get("utilization")),
        temperature_limit_celsius=temperature_limit_celsius,
    )


def _snapshot_from_metrics(
    *,
    temperature: float | None,
    power: float | None,
    core_utilization: float | None,
    temperature_limit_celsius: float | None,
) -> SoAIBenchTelemetrySnapshot:
    unavailable_sensors = _unavailable_sensors(temperature=temperature, power=power)
    telemetry_available = not unavailable_sensors
    summary: JSONDict = {
        "telemetry_available": telemetry_available,
        "unavailable_sensors": list(unavailable_sensors),
        "throttle_detected": False,
    }
    if temperature is not None:
        summary["temperature_celsius"] = temperature
        summary["max_temperature_celsius"] = temperature
    if power is not None:
        summary["avg_power_watts"] = power
        summary["max_power_watts"] = power
    if core_utilization is not None:
        summary["core_utilization_percent"] = core_utilization
    if temperature_limit_celsius is not None:
        summary["temperature_limit_celsius"] = temperature_limit_celsius
    temperature_exceeded = (
        temperature is not None
        and temperature_limit_celsius is not None
        and temperature > temperature_limit_celsius
    )
    if temperature_exceeded:
        return _snapshot(
            summary,
            telemetry_available=telemetry_available,
            temperature_available=True,
            power_available=power is not None,
            temperature_exceeded=True,
            instability_reason="temperature_limit_exceeded",
            instability_message=(
                f"GPU temperature {temperature:.1f}C exceeded limit "
                f"{temperature_limit_celsius:.1f}C."
            ),
        )
    return _snapshot(
        summary,
        telemetry_available=telemetry_available,
        temperature_available=temperature is not None,
        power_available=power is not None,
    )


def settings_snapshot_from_gpu(gpu: JSONDict) -> JSONDict:
    clock = coerce_json_dict_or_empty(gpu.get("clock"))
    return _compact_snapshot(
        {
            "power_limit_watts": gpu.get("power_limit_watts"),
            "fan_speed": gpu.get("fan_speed"),
            "core_clock_mhz": gpu.get("core_clock_mhz") or clock.get("core_mhz"),
            "mem_clock_mhz": gpu.get("mem_clock_mhz") or clock.get("memory_mhz"),
        },
    )


def _snapshot(
    summary: JSONDict,
    *,
    telemetry_available: bool = False,
    temperature_available: bool = False,
    power_available: bool = False,
    temperature_exceeded: bool = False,
    instability_reason: str | None = None,
    instability_message: str | None = None,
) -> SoAIBenchTelemetrySnapshot:
    return SoAIBenchTelemetrySnapshot(
        summary=summary,
        telemetry_available=telemetry_available,
        temperature_available=temperature_available,
        power_available=power_available,
        temperature_exceeded=temperature_exceeded,
        instability_reason=instability_reason,
        instability_message=instability_message,
    )


def _compact_snapshot(values: JSONDict) -> JSONDict:
    snapshot: JSONDict = {}
    for key, value in values.items():
        if _is_present(value):
            snapshot[key] = value
    return snapshot


def _is_present(value: JSONValue) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _numeric(value: JSONValue) -> float | None:
    return coerce_float_from_json(
        value,
        default=None,
        allow_bool=False,
        allow_nonfinite=False,
    )


def _max_value(current: float | None, value: float) -> float:
    if current is None:
        return value
    return max(current, value)


def _unavailable_sensors(*, temperature: float | None, power: float | None) -> tuple[str, ...]:
    unavailable: list[str] = []
    if temperature is None:
        unavailable.append("temperature")
    if power is None:
        unavailable.append("power")
    return tuple(unavailable)
