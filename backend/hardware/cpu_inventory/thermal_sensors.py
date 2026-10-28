"""SoAI - Linux CPU thermal ownership and deterministic sampling [backend/hardware/cpu_inventory/thermal_sensors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from core.errors.exception_logging import log_handled_exception
from core.filesystem.open_files import open_text
from core.logging.trace import get_logger
from core.validation.numbers import coerce_float_from_json

OPERATION_HARDWARE_CPU_THERMAL_INVENTORY = "hardware.cpu.thermal.inventory"
OPERATION_HARDWARE_CPU_THERMAL_READ = "hardware.cpu.thermal.read"


__all__ = (
    "LOGGER_NAME",
    "LINUX_THERMAL_TEMP_INVALID",
    "CpuThermalSample",
    "CpuThermalReadings",
    "read_cpu_temperatures",
)

LOGGER_NAME = "SoAI.hardware.cpu_inventory.thermal_sensors"
LINUX_THERMAL_TEMP_INVALID = -274000


@dataclass(frozen=True, slots=True)
class CpuThermalSample:
    sensor_path: str
    sensor_label: str | None
    sensor_family: str
    scope: str
    package_id: int | None
    temperature_celsius: float


@dataclass(frozen=True, slots=True)
class CpuThermalReadings:
    package_temperatures: dict[int, float]
    aggregate_temperature: float | None
    single_package_temperature: float | None
    sources: tuple[CpuThermalSample, ...]


def _read_sensor_text(path: str) -> str | None:
    try:
        with open_text(path, encoding="utf-8") as file_handle:
            return file_handle.read().strip()
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="CPU thermal sensor unavailable.",
            operation=OPERATION_HARDWARE_CPU_THERMAL_READ,
            details={"sensor_path": path},
            level="trace",
        )
        return None


def _sensor_entries(base: str) -> list[str]:
    try:
        return sorted(os.listdir(base))
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="CPU thermal inventory unavailable.",
            operation=OPERATION_HARDWARE_CPU_THERMAL_INVENTORY,
            details={"sensor_path": base},
            level="trace",
        )
        return []


def _millidegrees(path: str) -> float | None:
    value = coerce_float_from_json(_read_sensor_text(path), default=None)
    if value is None or value in (-2147483648, 2147483647, LINUX_THERMAL_TEMP_INVALID):
        return None
    return value / 1000


def read_cpu_temperatures() -> CpuThermalReadings:
    package_samples: dict[int, list[float]] = {}
    aggregate_samples: list[float] = []
    unassigned_core_samples: dict[str, list[float]] = {}
    sources: list[CpuThermalSample] = []
    base = "/sys/class/hwmon"
    for entry in _sensor_entries(base):
        path = os.path.join(base, entry)
        name = _read_sensor_text(os.path.join(path, "name"))
        if name not in ("coretemp", "cpu_thermal", "k10temp"):
            continue
        for filename in _sensor_entries(path):
            if re.fullmatch(r"temp[0-9]+_input", filename) is None:
                continue
            value = _millidegrees(os.path.join(path, filename))
            if value is None:
                continue
            label = (
                _read_sensor_text(os.path.join(path, filename.replace("_input", "_label")))
                if name != "cpu_thermal"
                else None
            )
            package_match = re.fullmatch(r"Package id ([0-9]+)", label or "")
            if name == "coretemp" and package_match:
                package_id = int(package_match.group(1))
                if package_id not in package_samples:
                    package_samples[package_id] = []
                package_samples[package_id].append(value)
                sources.append(
                    CpuThermalSample(
                        os.path.join(path, filename), label, name, "package", package_id, value
                    )
                )
            elif name == "coretemp" and re.fullmatch(r"Core ?[0-9]+", label or ""):
                if path not in unassigned_core_samples:
                    unassigned_core_samples[path] = []
                unassigned_core_samples[path].append(value)
                sources.append(
                    CpuThermalSample(
                        os.path.join(path, filename), label, name, "single_package", None, value
                    )
                )
            elif name == "cpu_thermal" or (name == "k10temp" and label == "Tdie"):
                aggregate_samples.append(value)
                sources.append(
                    CpuThermalSample(
                        os.path.join(path, filename), label, name, "aggregate", None, value
                    )
                )
    if not package_samples and not aggregate_samples:
        base = "/sys/class/thermal"
        for entry in _sensor_entries(base):
            if re.fullmatch(r"thermal_zone[0-9]+", entry) is None:
                continue
            path = os.path.join(base, entry)
            sensor_type = _read_sensor_text(os.path.join(path, "type"))
            if sensor_type is None:
                continue
            if (
                re.fullmatch(
                    r"(?:cpu-[0-9]+-[0-9]+-step|cpuss-[0-9]+-usr|cpu_thermal)", sensor_type or ""
                )
                is None
            ):
                continue
            value = _millidegrees(os.path.join(path, "temp"))
            if value is not None:
                aggregate_samples.append(value)
                sources.append(
                    CpuThermalSample(
                        os.path.join(path, "temp"),
                        sensor_type,
                        sensor_type,
                        "aggregate",
                        None,
                        value,
                    )
                )
    single_package_temperature = None
    if len(unassigned_core_samples) == 1:
        for samples in unassigned_core_samples.values():
            single_package_temperature = max(samples)
    return CpuThermalReadings(
        {package: max(samples) for package, samples in package_samples.items()},
        max(aggregate_samples) if aggregate_samples else None,
        single_package_temperature,
        tuple(sources),
    )
