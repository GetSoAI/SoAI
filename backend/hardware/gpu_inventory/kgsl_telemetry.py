"""SoAI - Physically confined KGSL clock, busy and temperature telemetry [backend/hardware/gpu_inventory/kgsl_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Callable
from os.path import join, realpath
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.timing.epoch import epoch_ms
from hardware.cpu_inventory.thermal_sensors import LINUX_THERMAL_TEMP_INVALID
from hardware.gpu_inventory.sysfs_metrics import read_sysfs_metric, read_sysfs_text

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("PLATFORM_TELEMETRY_UNAVAILABLE", "read_kgsl_telemetry")

PLATFORM_TELEMETRY_UNAVAILABLE = "platform_telemetry_unavailable"
NATIVE_OBSERVATION_INVALID = "native_observation_invalid"
PERMISSION_DENIED = "permission_denied"
_HZ_PER_MHZ = 1_000_000
_MILLIDEGREES_PER_CELSIUS = 1000
_THERMAL_SENTINELS = (-2147483648, 2147483647, LINUX_THERMAL_TEMP_INVALID)
_BUSY_PERCENTAGE_PATTERN = r"(\d{1,3}) ?%"
_FAILURE_PRIORITY = (PERMISSION_DENIED, NATIVE_OBSERVATION_INVALID, PLATFORM_TELEMETRY_UNAVAILABLE)


def read_kgsl_telemetry(node: str, device: str) -> JSONDict:
    try:
        kgsl_node = realpath(node, strict=True)
        if not kgsl_node.startswith(f"{device}/"):
            raise ValidationError("KGSL telemetry node escapes its physical device.")
        clock_mhz, clock_failure = _read_operand(kgsl_node, "gpuclk", _clock_mhz)
        busy_percentage, busy_failure = _read_operand(
            kgsl_node, "gpu_busy_percentage", _busy_percentage
        )
        temperature, temperature_failure = _read_operand(kgsl_node, "temp", _temperature_celsius)
        if (
            realpath(node, strict=True) != kgsl_node
            or realpath(join(node, "device"), strict=True) != device
        ):
            raise StateError("KGSL physical identity changed during telemetry acquisition.")
    except PermissionError:
        return _unavailable(PERMISSION_DENIED)
    except OSError:
        return _unavailable(PLATFORM_TELEMETRY_UNAVAILABLE)
    except (StateError, ValidationError):
        return _unavailable(NATIVE_OBSERVATION_INVALID)
    if clock_mhz is None and busy_percentage is None and temperature is None:
        failures = (clock_failure, busy_failure, temperature_failure)
        return _unavailable(next(reason for reason in _FAILURE_PRIORITY if reason in failures))
    return {
        "core_clock_mhz": clock_mhz,
        "utilization": busy_percentage,
        "temperature": temperature,
        "telemetry_available": True,
        "telemetry_unavailable_reason": None,
        "telemetry_observed_at_ms": epoch_ms(),
    }


def _read_operand(
    kgsl_node: str, name: str, parse: Callable[[str], float | None]
) -> tuple[float | None, str | None]:
    path = join(kgsl_node, name)
    try:
        if realpath(path, strict=True) != path:
            return (None, NATIVE_OBSERVATION_INVALID)
        value = parse(path)
    except PermissionError:
        return (None, PERMISSION_DENIED)
    except OSError:
        return (None, PLATFORM_TELEMETRY_UNAVAILABLE)
    return (value, None) if value is not None else (None, NATIVE_OBSERVATION_INVALID)


def _clock_mhz(path: str) -> float | None:
    clock_hz = read_sysfs_metric(path)
    if clock_hz is None or not clock_hz.is_integer() or clock_hz <= 0:
        return None
    return clock_hz / _HZ_PER_MHZ


def _busy_percentage(path: str) -> float | None:
    text = read_sysfs_text(path)
    match = re.fullmatch(_BUSY_PERCENTAGE_PATTERN, text) if text is not None else None
    if match is None or int(match.group(1)) > 100:
        return None
    return float(match.group(1))


def _temperature_celsius(path: str) -> float | None:
    millidegrees = read_sysfs_metric(path)
    if millidegrees is None or not millidegrees.is_integer() or millidegrees in _THERMAL_SENTINELS:
        return None
    return millidegrees / _MILLIDEGREES_PER_CELSIUS


def _unavailable(reason: str) -> JSONDict:
    return {
        "core_clock_mhz": None,
        "utilization": None,
        "temperature": None,
        "telemetry_available": False,
        "telemetry_unavailable_reason": reason,
    }
