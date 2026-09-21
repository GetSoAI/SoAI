"""SoAI - SoAIBench GPU telemetry snapshots [backend/hardware/soaibench/telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.numbers import coerce_float_from_json
from hardware.control_snapshots import find_gpu_entry
from hardware.soaibench.amd_telemetry import read_amd_fast_telemetry
from hardware.soaibench.nvidia_telemetry import read_nvidia_fast_telemetry
from hardware.soaibench.telemetry_aggregation import SoAIBenchTelemetryAccumulator
from hardware.soaibench.telemetry_observation import SoAIBenchTelemetrySnapshot

if TYPE_CHECKING:
    from core.hardware.protocols import HardwareManagerProtocol
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SoAIBenchTelemetryAccumulator",
    "SoAIBenchTelemetryDiagnostics",
    "SoAIBenchTelemetrySnapshot",
    "read_soaibench_telemetry_snapshot",
    "settings_snapshot_from_gpu",
)

TELEMETRY_READ_OPERATION = "hardware.soaibench.telemetry.read"


@dataclass(slots=True)
class SoAIBenchTelemetryDiagnostics:
    provider_failure_active: bool = False


async def read_soaibench_telemetry_snapshot(
    hardware_manager: HardwareManagerProtocol,
    *,
    device_id: str,
    temperature_limit_celsius: float | None,
    logger: LoggerProtocol,
    diagnostics: SoAIBenchTelemetryDiagnostics,
) -> SoAIBenchTelemetrySnapshot:
    try:
        snapshot = await _acquire_soaibench_telemetry_snapshot(
            hardware_manager,
            device_id=device_id,
            temperature_limit_celsius=temperature_limit_celsius,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        if not diagnostics.provider_failure_active:
            log_exception(
                logger,
                exception,
                message="SoAIBench telemetry provider became unavailable (non-critical).",
                operation=TELEMETRY_READ_OPERATION,
                level="trace",
            )
        diagnostics.provider_failure_active = True
        return _unavailable_snapshot(
            "telemetry_provider_unavailable",
            temperature_limit_celsius=temperature_limit_celsius,
        )
    diagnostics.provider_failure_active = False
    return snapshot


async def _acquire_soaibench_telemetry_snapshot(
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
            throttle_detected=_optional_bool(fast_telemetry.get("throttle_detected")),
            temperature_limit_celsius=temperature_limit_celsius,
            diagnostic_code=_optional_string(fast_telemetry.get("diagnostic_code")),
        )
    snapshot = await hardware_manager.get_system_info(["gpu"], cache=False)
    gpu = find_gpu_entry(snapshot, device_id)
    if gpu is None:
        return _unavailable_snapshot(
            "gpu_telemetry_unavailable",
            temperature_limit_celsius=temperature_limit_celsius,
        )
    return _snapshot_from_metrics(
        temperature=_numeric(gpu.get("temperature")),
        power=_numeric(gpu.get("power_draw_watts")),
        core_utilization=_numeric(gpu.get("utilization")),
        throttle_detected=None,
        temperature_limit_celsius=temperature_limit_celsius,
        diagnostic_code=None,
    )


def _snapshot_from_metrics(
    *,
    temperature: float | None,
    power: float | None,
    core_utilization: float | None,
    throttle_detected: bool | None,
    temperature_limit_celsius: float | None,
    diagnostic_code: str | None,
) -> SoAIBenchTelemetrySnapshot:
    temperature_exceeded = (
        temperature is not None
        and temperature_limit_celsius is not None
        and temperature > temperature_limit_celsius
    )
    if temperature_exceeded:
        return SoAIBenchTelemetrySnapshot(
            temperature_celsius=temperature,
            power_watts=power,
            utilization_percent=core_utilization,
            throttle_detected=throttle_detected,
            temperature_limit_celsius=temperature_limit_celsius,
            temperature_exceeded=True,
            instability_reason="temperature_limit_exceeded",
            instability_message=(
                f"GPU temperature {temperature:.1f}C exceeded limit "
                f"{temperature_limit_celsius:.1f}C."
            ),
            diagnostic_code=diagnostic_code,
        )
    return SoAIBenchTelemetrySnapshot(
        temperature_celsius=temperature,
        power_watts=power,
        utilization_percent=core_utilization,
        throttle_detected=throttle_detected,
        temperature_limit_celsius=temperature_limit_celsius,
        temperature_exceeded=False,
        instability_reason=None,
        instability_message=None,
        diagnostic_code=diagnostic_code,
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


def _unavailable_snapshot(
    diagnostic_code: str,
    *,
    temperature_limit_celsius: float | None,
) -> SoAIBenchTelemetrySnapshot:
    return SoAIBenchTelemetrySnapshot(
        temperature_celsius=None,
        power_watts=None,
        utilization_percent=None,
        throttle_detected=None,
        temperature_limit_celsius=temperature_limit_celsius,
        temperature_exceeded=False,
        instability_reason=None,
        instability_message=None,
        diagnostic_code=diagnostic_code,
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


def _optional_bool(value: JSONValue) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_string(value: JSONValue) -> str | None:
    return value if isinstance(value, str) and value else None
